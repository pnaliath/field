from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v022 = root / "fl-native-visualizer-v022"

# Start from compile-green V0.22. V0.23 separates four concepts that had been
# incorrectly coupled: live mixer pan, continuous stereo width, discrete L/R
# event voices, and absolute per-source depth. It also ports the web renderer's
# actual low-density ring/lobe grammar rather than the heavy outlined-polygons look.
runpy.run_path(str(v022 / "generate_v022.py"), run_name="__main__")
src = v022 / "generated" / "fieldv022.cpp"
out = here / "generated" / "fieldv023.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.23 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.23 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.23 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


def replace_function(signature: str, replacement: str, label: str) -> None:
    global text
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"V0.23 could not find function: {label}")
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f"V0.23 could not find opening brace: {label}")
    depth = 0
    end = -1
    for i in range(brace, len(text)):
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise RuntimeError(f"V0.23 could not find closing brace: {label}")
    text = text[:start] + replacement + text[end:]


# Identity / diagnostics filename.
text = text.replace("Field V0.22", "Field V0.23")
text = text.replace("FieldV022", "FieldV023")
text = text.replace("V022", "V023")
text = text.replace("v022", "v023")
text = text.replace("FieldV022_diagnostics.csv", "FieldV023_diagnostics.csv")
text = text.replace("STABLE ROOM + STEREO", "WEB GEOMETRY + LIVE PAN")

# -----------------------------------------------------------------------------
# Independent real-time spatial telemetry. Do NOT reuse the cumulative learned
# routeBalance for mixer-pan response: that value intentionally converges slowly
# and was the direct cause of the very laggy runtime pan seen in V0.22.
replace_once(
    "    std::array<std::atomic<float>, kMaxRoutes> routeWidth;\n",
    "    std::array<std::atomic<float>, kMaxRoutes> routeWidth;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeLivePan;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeLiveWidth;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeDepthLevelDb;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeSpatialPanShift;\n",
    "live pan width depth state",
)

replace_once(
    "        for (auto& p : routeWidth)\n            p.store (0.0f, std::memory_order_relaxed);",
    "        for (auto& p : routeWidth)\n"
    "            p.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& p : routeLivePan) p.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& p : routeLiveWidth) p.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& p : routeDepthLevelDb) p.store (-120.0f, std::memory_order_relaxed);\n"
    "        for (auto& p : routeSpatialPanShift) p.store (0.0f, std::memory_order_relaxed);",
    "live spatial initialization",
)

live_spatial_update = r'''            // V0.23 live spatial path. Pan follows the current audio in a few blocks;
            // continuous stereo width is slower so the body does not breathe on every sample.
            if (targetPeakDb > -114.0f)
            {
                const float oldPan = routeLivePan[routeArrayIndex].load (std::memory_order_relaxed);
                const float panDelta = balance - oldPan;
                const float panAlpha = std::abs (panDelta) > 0.22f ? 0.82f : 0.58f;
                routeLivePan[routeArrayIndex].store (
                    std::clamp (oldPan + panDelta * panAlpha, -1.0f, 1.0f),
                    std::memory_order_relaxed);

                const float oldWidth = routeLiveWidth[routeArrayIndex].load (std::memory_order_relaxed);
                routeLiveWidth[routeArrayIndex].store (
                    clamp01 (oldWidth + (width - oldWidth) * 0.075f),
                    std::memory_order_relaxed);

                const float activeRmsDb = linearToDb (std::max (1.0e-9f, static_cast<float> (fastRms)));
                if (activeRmsDb > -90.0f)
                {
                    const float oldDepthDb = routeDepthLevelDb[routeArrayIndex].load (std::memory_order_relaxed);
                    const float depthAlpha = oldDepthDb <= -119.0f ? 1.0f :
                        (activeRmsDb > oldDepthDb ? 0.13f : 0.035f);
                    routeDepthLevelDb[routeArrayIndex].store (
                        oldDepthDb <= -119.0f ? activeRmsDb :
                            oldDepthDb + (activeRmsDb - oldDepthDb) * depthAlpha,
                        std::memory_order_relaxed);
                }

                // For a learned L/R pair, estimate a common pan shift rather than
                // moving the pair toward whichever hat/voice happens to fire now.
                if (spatialVoiceCount[routeArrayIndex].load (std::memory_order_acquire) >= 2)
                {
                    const float c0 = spatialVoicePan[routeArrayIndex][0].load (std::memory_order_relaxed);
                    const float c1 = spatialVoicePan[routeArrayIndex][1].load (std::memory_order_relaxed);
                    const float nearest = std::abs (balance - c0) <= std::abs (balance - c1) ? c0 : c1;
                    const float residual = std::clamp (balance - nearest, -0.85f, 0.85f);
                    const float oldShift = routeSpatialPanShift[routeArrayIndex].load (std::memory_order_relaxed);
                    routeSpatialPanShift[routeArrayIndex].store (
                        oldShift + (residual - oldShift) * 0.50f, std::memory_order_relaxed);
                }
            }
'''
replace_once(
    "            updateSpatialVoices (routeArrayIndex, balance, static_cast<float> (fastRms));\n",
    "            updateSpatialVoices (routeArrayIndex, balance, static_cast<float> (fastRms));\n" + live_spatial_update,
    "live spatial update",
)

# A split must be present in the RECENT event pattern, not merely in old history.
# This prevents a manual pan move from being mistaken for two simultaneous voices.
replace_once(
    "            if (!accepted)\n                continue;\n\n            for (int j = 0; j < kTry; ++j)",
    "            if (accepted && kTry == 2)\n"
    "            {\n"
    "                int recent0 = 0, recent1 = 0;\n"
    "                const int recentN = std::min (6, n);\n"
    "                for (int ii = n - recentN; ii < n; ++ii)\n"
    "                {\n"
    "                    const float p = pans[static_cast<size_t> (ii)];\n"
    "                    if (std::abs (p - centres[0]) <= std::abs (p - centres[1])) ++recent0;\n"
    "                    else ++recent1;\n"
    "                }\n"
    "                if (recent0 < 2 || recent1 < 2) accepted = false;\n"
    "            }\n"
    "            if (!accepted)\n"
    "                continue;\n\n"
    "            for (int j = 0; j < kTry; ++j)",
    "recent recurrence split gate",
)

# -----------------------------------------------------------------------------
# Render topology: one broad body for continuous stereo; two compact bodies only
# for a true recurrent L/R event split. The split positions get a common live pan
# shift, while a single body's centre follows live pan directly.
spatial_expand = r'''        std::vector<DrawTrack> spatialActive;
        spatialActive.reserve (active.size () * 2u);
        for (const auto& sourceTrack : active)
        {
            if (!sourceTrack.meta || sourceTrack.meta->routeIndex < 1 || sourceTrack.meta->routeIndex > kMaxRoutes)
                continue;
            const size_t idx = static_cast<size_t> (sourceTrack.meta->routeIndex - 1);
            const int voices = std::clamp (spatialVoiceCount[idx].load (std::memory_order_acquire), 1, 2);
            const float livePan = routeLivePan[idx].load (std::memory_order_relaxed);
            const float liveWidth = routeLiveWidth[idx].load (std::memory_order_relaxed);

            if (voices <= 1)
            {
                DrawTrack d = sourceTrack;
                d.spatialVoiceIndex = 0;
                d.spatialVoiceCount = 1;
                d.balance = livePan;
                d.width = liveWidth;
                spatialActive.push_back (d);
                continue;
            }

            const float shift = routeSpatialPanShift[idx].load (std::memory_order_relaxed);
            for (int voice = 0; voice < voices; ++voice)
            {
                DrawTrack d = sourceTrack;
                d.spatialVoiceIndex = voice;
                d.spatialVoiceCount = voices;
                const float learnedCentre = spatialVoicePan[idx][static_cast<size_t> (voice)].load (std::memory_order_relaxed);
                d.balance = std::clamp (learnedCentre + shift, -1.0f, 1.0f);
                d.width = liveWidth;
                spatialActive.push_back (d);
            }
        }
        active = std::move (spatialActive);

'''
replace_between(
    "        std::vector<DrawTrack> spatialActive;",
    "        // Absolute per-source depth calibration.",
    spatial_expand,
    "separate live pan continuous width and split voices",
)

# -----------------------------------------------------------------------------
# Depth is absolute per route, but now uses active audio RMS rather than the
# spectral percentile loudness that severely under-estimates sparse percussion.
depth_block = r'''        // V0.23 absolute depth from active source RMS. This is independent per track:
        // one fader can never redistribute any other source's Z position.
        for (auto& track : active)
        {
            if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
                continue;
            const size_t idx = static_cast<size_t> (track.meta->routeIndex - 1);
            float levelDb = routeDepthLevelDb[idx].load (std::memory_order_relaxed);
            if (levelDb <= -119.0f)
                levelDb = -48.0f;

            // -14 dB RMS ~= front, -72 dB RMS ~= deep back. No session-relative min/max.
            const float backness = clamp01 ((-14.0f - levelDb) / 58.0f);
            const float targetDepth = 0.10f + backness * 0.72f;
            float& smoothDepth = spatialDepth[idx];
            if (smoothDepth <= 0.001f)
                smoothDepth = targetDepth;
            else
                smoothDepth += (targetDepth - smoothDepth) * 0.075f;
            track.visualZ = std::clamp (smoothDepth, 0.08f, 0.84f);
            const float frontness = 1.0f - backness;
            track.volumeThickness = 0.040f + frontness * 0.075f;
        }

'''
replace_between(
    "        // Absolute per-source depth calibration.",
    "        std::vector<DrawTrack> renderOrder = active;",
    depth_block,
    "active RMS absolute depth",
)

# -----------------------------------------------------------------------------
# Exact-ish browser rendering grammar:
# - true lobe runs, merge <=2-band gaps, discard <2-band runs
# - semicircular taper across each lobe
# - subtle filled rings, contour only every fourth band
# - thin silhouette that closes one band outside the lobe
# - per-lobe shadow and small upper-left highlight
# This replaces V0.17's much heavier every-ring outline.
web_body = r'''    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)
    {
        if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
            return;
        const size_t routeIndex = static_cast<size_t> (track.meta->routeIndex - 1);
        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))
            return;
        const float presence = visualPresenceForTrack (track);
        if (presence <= 0.010f)
            return;

        std::array<float, kBands> shape {};
        for (int i = 0; i < kBands; ++i)
            shape[static_cast<size_t> (i)] = learnedShapeEnergy (routeIndex, i);

        std::vector<std::pair<int, int>> rawRuns;
        for (int i = 0; i < kBands; )
        {
            while (i < kBands && shape[static_cast<size_t> (i)] <= kShapeGate) ++i;
            if (i >= kBands) break;
            const int a = i;
            while (i + 1 < kBands && shape[static_cast<size_t> (i + 1)] > kShapeGate) ++i;
            rawRuns.push_back ({a, i});
            ++i;
        }

        std::vector<std::pair<int, int>> lobes;
        for (const auto& r : rawRuns)
        {
            if (!lobes.empty () && r.first - lobes.back ().second - 1 <= 2)
                lobes.back ().second = r.second;
            else
                lobes.push_back (r);
        }
        lobes.erase (std::remove_if (lobes.begin (), lobes.end (),
            [] (const auto& r) { return r.second - r.first + 1 < 2; }), lobes.end ());
        if (lobes.empty ())
            return;

        auto lobeForBand = [&] (int band) -> std::pair<int, int>
        {
            for (const auto& r : lobes)
                if (band >= r.first && band <= r.second) return r;
            return {-1, -1};
        };

        auto baseHalfPan = [&] ()
        {
            if (track.spatialVoiceCount > 1)
                return 0.30f * 0.52f; // browser multi-voice compact body
            // Map measured continuous stereo to the browser's width control range.
            // Mono remains a readable body; genuinely wide material can occupy much
            // more of L-R without being split into fake duplicate objects.
            const float webWidth = 0.35f + 2.35f * clamp01 (track.width);
            return 0.30f * (0.26f + 0.86f * (webWidth * 0.5f));
        };

        auto radiusForBand = [&] (int band, float swell)
        {
            if (band < 0 || band >= kBands)
                return 0.0f;
            const auto lobe = lobeForBand (band);
            if (lobe.first < 0)
                return 0.0f;
            const float s = shape[static_cast<size_t> (band)];
            if (s <= kShapeGate)
                return 0.0f;
            float round = 1.0f;
            if (lobe.second > lobe.first)
            {
                const float u = (static_cast<float> (band - lobe.first) /
                    static_cast<float> (lobe.second - lobe.first)) * 2.0f - 1.0f;
                round = std::sqrt (std::max (0.0f, 1.0f - u * u * 0.94f));
            }
            return baseHalfPan () * std::pow (s, 0.55f) * round * swell;
        };

        constexpr int kRingSegments = 18;
        const float frontness = 1.0f - clamp01 ((track.visualZ - 0.08f) / 0.76f);
        const float depthGain = 0.50f + 0.85f * frontness;
        auto makeRing = [&] (int band, float swell, float yOverride, bool floorRing)
        {
            std::array<POINT, kRingSegments + 1> pts {};
            const float rx = radiusForBand (band, swell);
            const float rz = rx / 1.70f * depthGain;
            const float hz = bandHz[static_cast<size_t> (band)].load (std::memory_order_relaxed);
            const float wy = floorRing ? yOverride : roomYForFrequency (hz);
            for (int k = 0; k <= kRingSegments; ++k)
            {
                const float th = static_cast<float> (k) / static_cast<float> (kRingSegments) * 6.28318530718f;
                const auto p = projectWorld (
                    track.balance + rx * std::cos (th), wy,
                    std::clamp (track.visualZ + rz * std::sin (th), 0.01f, 0.99f), area);
                pts[static_cast<size_t> (k)] = {p.x, p.y};
            }
            return pts;
        };

        const COLORREF raw = fieldRouteColor (*track.meta);
        const COLORREF roomBg = RGB (10, 14, 24);
        // Browser body opacity is intentionally tiny; simulated here by pre-mixing
        // toward the room background because plain GDI brushes have no alpha.
        const COLORREF bodyFill = mixColor (raw, roomBg,
            std::clamp (0.955f - presence * 0.045f - frontness * 0.018f, 0.86f, 0.96f));
        const COLORREF contour = mixColor (raw, roomBg,
            std::clamp (0.78f - presence * 0.16f - frontness * 0.05f, 0.50f, 0.82f));
        const COLORREF silhouette = mixColor (raw, RGB (215, 230, 245),
            std::clamp (0.30f - presence * 0.16f, 0.10f, 0.34f));

        // Per-lobe floor shadow, based on the lobe's own widest footprint.
        for (const auto& lobe : lobes)
        {
            int widestBand = lobe.first;
            float widest = 0.0f;
            for (int i = lobe.first; i <= lobe.second; ++i)
            {
                const float r = radiusForBand (i, 1.0f);
                if (r > widest) { widest = r; widestBand = i; }
            }
            if (widest <= 0.0f) continue;
            const auto shadow = makeRing (widestBand, 1.0f, 0.035f, true);
            HBRUSH sh = CreateSolidBrush (mixColor (RGB (0, 0, 0), roomBg, 0.24f + (1.0f - presence) * 0.30f));
            auto ob = SelectObject (dc, sh);
            auto op = SelectObject (dc, GetStockObject (NULL_PEN));
            Polygon (dc, shadow.data (), static_cast<int> (shadow.size ()));
            SelectObject (dc, op); SelectObject (dc, ob); DeleteObject (sh);
        }

        // Solid = all occupied rings, with NO per-ring outline.
        HBRUSH body = CreateSolidBrush (bodyFill);
        auto oldBrush = SelectObject (dc, body);
        auto oldPen = SelectObject (dc, GetStockObject (NULL_PEN));
        for (const auto& lobe : lobes)
            for (int i = lobe.first; i <= lobe.second; ++i)
                if (radiusForBand (i, 1.0f) > 0.0f)
                {
                    const auto ring = makeRing (i, 1.0f, 0.0f, false);
                    Polygon (dc, ring.data (), static_cast<int> (ring.size ()));
                }
        SelectObject (dc, oldPen); SelectObject (dc, oldBrush); DeleteObject (body);

        // Sparse contour rings: browser uses every fourth band.
        HPEN contourPen = CreatePen (PS_SOLID, 1, contour);
        oldPen = SelectObject (dc, contourPen);
        oldBrush = SelectObject (dc, GetStockObject (NULL_BRUSH));
        for (const auto& lobe : lobes)
            for (int i = lobe.first; i <= lobe.second; i += 4)
                if (radiusForBand (i, 1.0f) > 0.0f)
                {
                    const auto ring = makeRing (i, 1.0f, 0.0f, false);
                    Polyline (dc, ring.data (), static_cast<int> (ring.size ()));
                }
        SelectObject (dc, oldBrush); SelectObject (dc, oldPen); DeleteObject (contourPen);

        // Lobe silhouette closes one band outside the run, matching web lobePath().
        HPEN silhouettePen = CreatePen (PS_SOLID, 1, silhouette);
        oldPen = SelectObject (dc, silhouettePen);
        oldBrush = SelectObject (dc, GetStockObject (NULL_BRUSH));
        for (const auto& lobe : lobes)
        {
            const int lo = std::max (0, lobe.first - 1);
            const int hi = std::min (kBands - 1, lobe.second + 1);
            std::vector<POINT> outline;
            outline.reserve (static_cast<size_t> ((hi - lo + 1) * 2 + 1));
            for (int i = lo; i <= hi; ++i)
            {
                const float rx = (i < lobe.first || i > lobe.second) ? 0.0f : radiusForBand (i, 1.0f);
                const float hz = bandHz[static_cast<size_t> (i)].load (std::memory_order_relaxed);
                const auto p = projectWorld (track.balance + rx, roomYForFrequency (hz), track.visualZ, area);
                outline.push_back ({p.x, p.y});
            }
            for (int i = hi; i >= lo; --i)
            {
                const float rx = (i < lobe.first || i > lobe.second) ? 0.0f : radiusForBand (i, 1.0f);
                const float hz = bandHz[static_cast<size_t> (i)].load (std::memory_order_relaxed);
                const auto p = projectWorld (track.balance - rx, roomYForFrequency (hz), track.visualZ, area);
                outline.push_back ({p.x, p.y});
            }
            if (!outline.empty ())
            {
                outline.push_back (outline.front ());
                Polyline (dc, outline.data (), static_cast<int> (outline.size ()));
            }

            // Small upper-left specular cue: enough to read volume without making
            // the source look like a stack of neon hoops.
            int x0 = 100000, y0 = 100000, x1 = -100000, y1 = -100000;
            for (int i = lobe.first; i <= lobe.second; ++i)
            {
                const float rx = radiusForBand (i, 1.0f);
                const float hz = bandHz[static_cast<size_t> (i)].load (std::memory_order_relaxed);
                for (int side : {-1, 1})
                {
                    const auto p = projectWorld (track.balance + static_cast<float> (side) * rx,
                        roomYForFrequency (hz), track.visualZ, area);
                    x0 = std::min (x0, p.x); x1 = std::max (x1, p.x);
                    y0 = std::min (y0, p.y); y1 = std::max (y1, p.y);
                }
            }
            if (presence > 0.10f && x1 > x0 + 8 && y1 > y0 + 8)
            {
                const int ew = std::max (3, (x1 - x0) / 5);
                const int eh = std::max (2, (y1 - y0) / 9);
                const int ex = x0 + (x1 - x0) / 3 - ew / 2;
                const int ey = y0 + (y1 - y0) / 4 - eh / 2;
                HBRUSH hiBrush = CreateSolidBrush (mixColor (RGB (245, 250, 255), roomBg, 0.78f));
                auto hb = SelectObject (dc, hiBrush);
                auto hp = SelectObject (dc, GetStockObject (NULL_PEN));
                Ellipse (dc, ex, ey, ex + ew, ey + eh);
                SelectObject (dc, hp); SelectObject (dc, hb); DeleteObject (hiBrush);
            }
        }
        SelectObject (dc, oldBrush); SelectObject (dc, oldPen); DeleteObject (silhouettePen);
    }
'''
replace_function(
    "    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)",
    web_body,
    "web spectral body renderer",
)

# Banner text, if present.
text = text.replace(
    "V0.22 stable room: max 2 locked voices + smoother presence + forward Z",
    "V0.23: live pan + continuous width / discrete L-R + active-RMS Z + web lobe renderer"
)

out.write_text(text, encoding="utf-8")
print(out)
