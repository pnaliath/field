from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v016 = root / "fl-native-visualizer-v016"

runpy.run_path(str(v016 / "generate_v016.py"), run_name="__main__")
src = v016 / "generated" / "fieldv016.cpp"
out = here / "generated" / "fieldv017.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.17 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.17 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.17 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


# Fresh identity.
text = text.replace("Field V0.16", "Field V0.17")
text = text.replace("FieldV016", "FieldV017")
text = text.replace("V016", "V017")
text = text.replace("v016", "v017")

# -----------------------------------------------------------------------------
# Shape is relative to THIS source's own learned spectrum, not another track.
# Gain therefore moves a source in Z but does not make unrelated source shapes
# shrink/grow when a different track changes level.
shape_helper = r'''    float learnedShapeEnergy (size_t routeIndex, int band) const
    {
        if (routeIndex >= kMaxRoutes || band < 0 || band >= kBands)
            return 0.0f;
        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))
            return 0.0f;

        float ownPeakDb = -120.0f;
        for (int i = 0; i < kBands; ++i)
            ownPeakDb = std::max (ownPeakDb,
                routeProfileDb[routeIndex][static_cast<size_t> (i)].load (std::memory_order_relaxed));

        const float spectrumDb = routeProfileDb[routeIndex][static_cast<size_t> (band)].load (std::memory_order_relaxed);
        return clamp01 ((spectrumDb - (ownPeakDb - kShapeDynDb)) / kShapeDynDb);
    }

'''
replace_between(
    "    float learnedShapeEnergy (size_t routeIndex, int band) const\n    {",
    "    struct ProjectedPoint",
    shape_helper,
    "per-source learned spectral reference",
)

# -----------------------------------------------------------------------------
# Stable live-presence envelope. Geometry remains learned/static; this value only
# controls whether that learned body is visually lit. Short gaps between hits are
# held and released slowly, so repeated percussion does not randomly miss hits.
replace_once(
    "    std::array<std::atomic<float>, kMaxRoutes> routeLoudnessDb;\n",
    "    std::array<std::atomic<float>, kMaxRoutes> routeLoudnessDb;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeVisualPresence;\n"
    "    std::array<int, kMaxRoutes> routePresenceHoldBlocks {};\n",
    "presence state members",
)
replace_once(
    "        for (auto& loudness : routeLoudnessDb)\n"
    "            loudness.store (-120.0f, std::memory_order_relaxed);",
    "        for (auto& loudness : routeLoudnessDb)\n"
    "            loudness.store (-120.0f, std::memory_order_relaxed);\n"
    "        for (auto& presence : routeVisualPresence)\n"
    "            presence.store (0.0f, std::memory_order_relaxed);",
    "presence initialization",
)
replace_once(
    "            routeHasSignal[routeArrayIndex].store (hasSignal, std::memory_order_relaxed);\n",
    "            routeHasSignal[routeArrayIndex].store (hasSignal, std::memory_order_relaxed);\n"
    "            {\n"
    "                auto& presenceCell = routeVisualPresence[routeArrayIndex];\n"
    "                const float oldPresence = presenceCell.load (std::memory_order_relaxed);\n"
    "                float targetPresence = std::pow (\n"
    "                    clamp01 ((targetPeakDb + 110.0f) / 92.0f), 0.55f);\n"
    "                if (hasSignal && targetPresence > 0.025f)\n"
    "                    routePresenceHoldBlocks[routeArrayIndex] = 18;\n"
    "                else if (routePresenceHoldBlocks[routeArrayIndex] > 0)\n"
    "                {\n"
    "                    --routePresenceHoldBlocks[routeArrayIndex];\n"
    "                    targetPresence = std::max (targetPresence, oldPresence * 0.94f);\n"
    "                }\n"
    "                const float coefficient = targetPresence > oldPresence ? 0.46f : 0.045f;\n"
    "                presenceCell.store (clamp01 (oldPresence + (targetPresence - oldPresence) * coefficient),\n"
    "                    std::memory_order_relaxed);\n"
    "            }\n",
    "attack hold release presence envelope",
)

presence_helper = r'''    float visualPresenceForTrack (const DrawTrack& track) const
    {
        if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
            return 0.0f;
        return clamp01 (routeVisualPresence[static_cast<size_t> (track.meta->routeIndex - 1)].load (
            std::memory_order_relaxed));
    }

'''
replace_between(
    "    float visualPresenceForTrack (const DrawTrack& track) const\n    {",
    "    void drawFxAura",
    presence_helper,
    "presence helper uses held envelope",
)

# -----------------------------------------------------------------------------
# Absolute Z calibration. No min/max scan across the session. A change to one
# source can only move that source. The mapping is intentionally broad/clamped.
absolute_depth = r'''        // Absolute per-source depth calibration. No cross-track normalization:
        // changing one track's gain never moves another track in the room.
        for (auto& track : active)
        {
            if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
                continue;
            const size_t idx = static_cast<size_t> (track.meta->routeIndex - 1);
            if (!routeProfileReady[idx].load (std::memory_order_relaxed))
            {
                track.visualZ = 0.52f;
                track.volumeThickness = 0.060f;
                continue;
            }

            const float loudDb = routeLoudnessDb[idx].load (std::memory_order_relaxed);
            // Approx calibration: around -10 dB learned loudness is near-front,
            // around -55 dB is near-back. Values outside clamp without affecting peers.
            const float backness = clamp01 ((-10.0f - loudDb) / 45.0f);
            const float targetDepth = 0.14f + backness * 0.74f;
            float& smoothDepth = spatialDepth[idx];
            if (smoothDepth <= 0.001f)
                smoothDepth = targetDepth;
            else
                smoothDepth += (targetDepth - smoothDepth) * 0.035f;
            track.visualZ = std::clamp (smoothDepth, 0.12f, 0.90f);
            const float frontness = 1.0f - backness;
            track.volumeThickness = 0.042f + frontness * 0.070f;
        }

'''
replace_between(
    "        // Browser depth model: long-term loudness + duty, never instantaneous peak,\n",
    "        std::vector<DrawTrack> renderOrder = active;",
    absolute_depth,
    "absolute Z depth model",
)

# -----------------------------------------------------------------------------
# Web-app-style body: occupied frequency runs only, rendered as a stack of rings
# in the pan/depth plane. Missing low bands create NO geometry, so hats float at
# their actual spectral height rather than connecting to the floor.
ring_body = r'''    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)
    {
        if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
            return;
        const size_t routeIndex = static_cast<size_t> (track.meta->routeIndex - 1);
        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))
            return;
        const float presence = visualPresenceForTrack (track);
        if (presence <= 0.012f)
            return;

        const COLORREF raw = fieldRouteColor (*track.meta);
        const COLORREF bg = RGB (16, 20, 26);
        const COLORREF ringFill = mixColor (raw, bg, 0.91f - presence * 0.16f);
        const COLORREF ringLine = mixColor (raw, RGB (235, 245, 255), 0.64f - presence * 0.46f);
        const COLORREF silhouetteLine = mixColor (raw, RGB (244, 249, 255), 0.40f - presence * 0.30f);

        const float loudDb = routeLoudnessDb[routeIndex].load (std::memory_order_relaxed);
        const float backness = clamp01 ((-10.0f - loudDb) / 45.0f);
        const float depthRadiusGain = 0.55f + (1.0f - backness) * 0.78f;
        constexpr int kRingSegments = 22;

        auto radiusForBand = [&] (int band, float swell)
        {
            const float energy = learnedShapeEnergy (routeIndex, band);
            if (energy <= kShapeGate)
                return 0.0f;
            const float shaped = std::pow (energy, 0.55f);
            return (0.006f + shaped * (0.055f + track.width * 0.090f)) * swell;
        };

        auto makeRing = [&] (int band, float swell, float zOffset, float xOffset)
        {
            std::array<POINT, kRingSegments + 1> pts {};
            const float rx = radiusForBand (band, swell);
            const float rz = rx / 1.70f * depthRadiusGain;
            const float hz = bandHz[static_cast<size_t> (band)].load (std::memory_order_relaxed);
            const float wy = roomYForFrequency (hz);
            for (int k = 0; k <= kRingSegments; ++k)
            {
                const float th = static_cast<float> (k) / static_cast<float> (kRingSegments) * 6.28318530718f;
                const auto p = projectWorld (
                    track.balance + xOffset + rx * std::cos (th), wy,
                    std::clamp (track.visualZ + zOffset + rz * std::sin (th), 0.01f, 0.99f), area);
                pts[static_cast<size_t> (k)] = {p.x, p.y};
            }
            return pts;
        };

        // Shadow uses the actual widest occupied band, not a full-height extrusion.
        float maxRx = 0.0f;
        for (int band = 0; band < kBands; ++band)
            maxRx = std::max (maxRx, radiusForBand (band, 1.0f));
        if (maxRx > 0.0f)
        {
            std::array<POINT, kRingSegments + 1> shadow {};
            const float rz = maxRx / 1.70f * depthRadiusGain;
            for (int k = 0; k <= kRingSegments; ++k)
            {
                const float th = static_cast<float> (k) / static_cast<float> (kRingSegments) * 6.28318530718f;
                const auto p = projectWorld (
                    track.balance + maxRx * std::cos (th), 0.04f,
                    std::clamp (track.visualZ + rz * std::sin (th), 0.01f, 0.99f), area);
                shadow[static_cast<size_t> (k)] = {p.x, p.y};
            }
            HBRUSH shadowBrush = CreateSolidBrush (mixColor (RGB (0, 0, 0), bg, 0.32f + (1.0f - presence) * 0.45f));
            auto oldBrush = SelectObject (dc, shadowBrush);
            auto oldPen = SelectObject (dc, GetStockObject (NULL_PEN));
            Polygon (dc, shadow.data (), static_cast<int> (shadow.size ()));
            SelectObject (dc, oldPen); SelectObject (dc, oldBrush); DeleteObject (shadowBrush);
        }

        HBRUSH bodyBrush = CreateSolidBrush (ringFill);
        HPEN contourPen = CreatePen (PS_SOLID, 1, ringLine);
        auto oldBrush = SelectObject (dc, bodyBrush);
        auto oldPen = SelectObject (dc, contourPen);

        // Ring stack: exactly the browser visual grammar. Only occupied bands draw.
        for (int band = 0; band < kBands; ++band)
        {
            if (radiusForBand (band, 1.0f) <= 0.0f)
                continue;
            const auto ring = makeRing (band, 1.0f, 0.0f, 0.0f);
            Polygon (dc, ring.data (), static_cast<int> (ring.size ()));
        }
        SelectObject (dc, oldPen); SelectObject (dc, oldBrush);
        DeleteObject (contourPen); DeleteObject (bodyBrush);

        // Silhouette each contiguous occupied frequency lobe independently. This is
        // what prevents a high-frequency hat from acquiring a line down to 28 Hz.
        HPEN silhouettePen = CreatePen (PS_SOLID, 2, silhouetteLine);
        oldPen = SelectObject (dc, silhouettePen);
        oldBrush = SelectObject (dc, GetStockObject (NULL_BRUSH));
        int band = 0;
        while (band < kBands)
        {
            while (band < kBands && radiusForBand (band, 1.0f) <= 0.0f)
                ++band;
            if (band >= kBands)
                break;
            const int start = band;
            while (band + 1 < kBands && radiusForBand (band + 1, 1.0f) > 0.0f)
                ++band;
            const int end = band;

            std::vector<POINT> outline;
            outline.reserve (static_cast<size_t> ((end - start + 1) * 2 + 2));
            for (int i = start; i <= end; ++i)
            {
                const float rx = radiusForBand (i, 1.0f);
                const float hz = bandHz[static_cast<size_t> (i)].load (std::memory_order_relaxed);
                const auto p = projectWorld (track.balance + rx, roomYForFrequency (hz), track.visualZ, area);
                outline.push_back ({p.x, p.y});
            }
            for (int i = end; i >= start; --i)
            {
                const float rx = radiusForBand (i, 1.0f);
                const float hz = bandHz[static_cast<size_t> (i)].load (std::memory_order_relaxed);
                const auto p = projectWorld (track.balance - rx, roomYForFrequency (hz), track.visualZ, area);
                outline.push_back ({p.x, p.y});
            }
            if (!outline.empty ())
            {
                outline.push_back (outline.front ());
                Polyline (dc, outline.data (), static_cast<int> (outline.size ()));
            }
            ++band;
        }
        SelectObject (dc, oldBrush); SelectObject (dc, oldPen); DeleteObject (silhouettePen);
    }

'''
replace_between(
    "    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)\n    {",
    "    void drawTrackNameOnBody",
    ring_body,
    "web ring-stack body renderer",
)

# FX is a shell/echo around the SAME occupied bands, never a full-range polygon.
fx_body = r'''    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)
    {
        if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
            return;
        const size_t routeIndex = static_cast<size_t> (track.meta->routeIndex - 1);
        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))
            return;
        const float presence = visualPresenceForTrack (track);
        if (presence <= 0.012f || (reverbAmount <= 0.004f && delayAmount <= 0.004f))
            return;

        const COLORREF raw = fieldRouteColor (*track.meta);
        const COLORREF bg = RGB (16, 20, 26);
        constexpr int kSegments = 20;

        auto drawShellRing = [&] (int band, float swell, float zOffset, float xOffset, float fade)
        {
            const float energy = learnedShapeEnergy (routeIndex, band);
            if (energy <= kShapeGate)
                return;
            const float shaped = std::pow (energy, 0.55f);
            const float rx = (0.006f + shaped * (0.055f + track.width * 0.090f)) * swell;
            const float rz = rx / 1.70f;
            const float hz = bandHz[static_cast<size_t> (band)].load (std::memory_order_relaxed);
            const float wy = roomYForFrequency (hz);
            std::array<POINT, kSegments + 1> pts {};
            for (int k = 0; k <= kSegments; ++k)
            {
                const float th = static_cast<float> (k) / static_cast<float> (kSegments) * 6.28318530718f;
                const auto p = projectWorld (
                    track.balance + xOffset + rx * std::cos (th), wy,
                    std::clamp (track.visualZ + zOffset + rz * std::sin (th), 0.01f, 0.99f), area);
                pts[static_cast<size_t> (k)] = {p.x, p.y};
            }
            HPEN pen = CreatePen (PS_SOLID, 1, mixColor (raw, bg, fade));
            auto oldPen = SelectObject (dc, pen);
            auto oldBrush = SelectObject (dc, GetStockObject (NULL_BRUSH));
            Polygon (dc, pts.data (), static_cast<int> (pts.size ()));
            SelectObject (dc, oldBrush); SelectObject (dc, oldPen); DeleteObject (pen);
        };

        for (int band = 0; band < kBands; band += 3)
        {
            if (reverbAmount > 0.004f)
            {
                const float swell = 1.08f + reverbAmount * 0.55f;
                drawShellRing (band, swell, 0.020f + reverbAmount * 0.10f, 0.0f,
                    0.90f - presence * 0.16f);
            }
            if (delayAmount > 0.004f)
            {
                const float side = 0.025f + delayAmount * 0.10f;
                drawShellRing (band, 1.03f, 0.018f + delayAmount * 0.05f, -side,
                    0.90f - presence * 0.12f);
                drawShellRing (band, 1.02f, 0.030f + delayAmount * 0.08f, side,
                    0.94f - presence * 0.10f);
            }
        }
    }

'''
replace_between(
    "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)\n    {",
    "    bool shouldHideAsFxVisualReturn",
    fx_body,
    "frequency-cropped FX shells",
)

# Current V0.12 identity trace closes a full-range polygon. The new ring body already
# contains contours/silhouettes, so disable that obsolete overlay entirely.
identity_body = r'''    void drawIdentityTrace (HDC, const DrawTrack&, const RECT&)
    {
        // Ring stack + lobe silhouette now provide identity/readability.
    }

'''
replace_between(
    "    void drawIdentityTrace (HDC dc, const DrawTrack& track, const RECT& area)\n    {",
    "    void drawTrackNameOnBody",
    identity_body,
    "remove obsolete full-height identity trace",
)

# Label the dominant occupied band like the browser reference, rather than a fixed
# mid-height/rotated label which can float outside a cropped lobe.
label_body = r'''    void drawTrackNameOnBody (HDC dc, const DrawTrack& track, const RECT& area)
    {
        if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
            return;
        const size_t routeIndex = static_cast<size_t> (track.meta->routeIndex - 1);
        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))
            return;
        const float presence = visualPresenceForTrack (track);
        if (presence <= 0.055f)
            return;

        int bestBand = -1;
        float bestEnergy = kShapeGate;
        for (int band = 0; band < kBands; ++band)
        {
            const float energy = learnedShapeEnergy (routeIndex, band);
            if (energy > bestEnergy)
            {
                bestEnergy = energy;
                bestBand = band;
            }
        }
        if (bestBand < 0)
            return;

        std::string display = !track.meta->visibleName.empty () ? track.meta->visibleName : track.meta->userName;
        if (display.empty ())
            display = "Track " + std::to_string (track.meta->mixerIndex >= 0 ? track.meta->mixerIndex : track.meta->routeIndex);
        if (display.size () > 18)
            display = display.substr (0, 17) + "...";
        const auto wide = ansiToWide (display);
        if (wide.empty ())
            return;

        const float hz = bandHz[static_cast<size_t> (bestBand)].load (std::memory_order_relaxed);
        const auto anchor = projectWorld (track.balance, roomYForFrequency (hz),
            std::clamp (track.visualZ - 0.006f, 0.01f, 0.99f), area);

        HFONT labelFont = CreateFontW (-14, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        auto oldFont = SelectObject (dc, labelFont);
        SetBkMode (dc, TRANSPARENT);
        SetTextColor (dc, mixColor (RGB (245, 249, 253), RGB (16, 20, 26), 0.18f + (1.0f - presence) * 0.55f));
        RECT r {anchor.x - 90, anchor.y - 12, anchor.x + 90, anchor.y + 12};
        DrawTextW (dc, wide.c_str (), static_cast<int> (wide.size ()), &r,
            DT_CENTER | DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);
        SelectObject (dc, oldFont);
        DeleteObject (labelFont);
    }

'''
replace_between(
    "    void drawTrackNameOnBody (HDC dc, const DrawTrack& track, const RECT& area)\n    {",
    "    void paint (HWND hwnd)",
    label_body,
    "dominant-lobe body labels",
)

# Sidebar: only routes that have actually carried audio, but membership never
# changes again after everActive becomes true. FX diagnosis does not affect rows.
replace_once(
    "            const size_t idx = static_cast<size_t> (item.routeIndex - 1);\n"
    "            DrawTrack d;",
    "            const size_t idx = static_cast<size_t> (item.routeIndex - 1);\n"
    "            if (!everActive[idx].load (std::memory_order_relaxed))\n"
    "                continue;\n"
    "            DrawTrack d;",
    "stable audio-bearing sidebar membership",
)

text = text.replace(
    "Learned bodies stay geometrically fixed; live audio only fades presence. Routed track list is session-stable.",
    "Web-style lobes: occupied frequencies only, absolute per-track Z, held presence, stacked 3D rings."
)
text = text.replace(
    "X PAN   |   Y FREQUENCY   |   Z LONG-TERM LOUDNESS",
    "X PAN   |   Y FREQUENCY   |   Z ABSOLUTE LOUDNESS"
)

out.write_text(text, encoding="utf-8")
print(out)
