from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v031 = root / "fl-native-visualizer-v031"

# Renderer-only branch from the last user-tested behavior base (V0.31).
# Do not inherit V0.32 analysis/shape-timing experiments here.
runpy.run_path(str(v031 / "generate_v031.py"), run_name="__main__")
src = v031 / "generated" / "fieldv031.cpp"
out = here / "generated" / "fieldv033.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_function(signature: str, replacement: str, label: str) -> None:
    global text
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"V0.33 could not find function: {label}")
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f"V0.33 could not find opening brace: {label}")
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
        raise RuntimeError(f"V0.33 could not find closing brace: {label}")
    text = text[:start] + replacement + text[end:]


# Identity only. Behavior and analyser stay V0.31.
text = text.replace("Field V0.31", "Field V0.33")
text = text.replace("FieldV031", "FieldV033")
text = text.replace("V031", "V033")
text = text.replace("v031", "v033")
text = text.replace("FieldV031_diagnostics.csv", "FieldV033_diagnostics.csv")
text = text.replace("STABLE DUAL VOICES", "WEB RENDER PARITY")

# Plain GDI was faking browser alpha by pre-mixing colours into the room background.
# Use GDI+ SourceOver alpha and anti-aliasing so stacked rings actually accumulate
# like the HTML canvas renderer.
inc = "#include <windows.h>"
if inc not in text:
    inc = "#include <Windows.h>"
if inc not in text:
    raise RuntimeError("V0.33 could not find windows include")
text = text.replace(inc, inc + "\n#include <gdiplus.h>", 1)

web_renderer = r'''    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)
    {
        if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
            return;
        const size_t routeIndex = static_cast<size_t> (track.meta->routeIndex - 1);
        if (!routeDisplayProfileReady[routeIndex].load (std::memory_order_acquire))
            return;

        const float presence = visualPresenceForTrack (track);
        if (presence <= 0.010f)
            return;

        std::array<float, kBands> shape {};
        for (int i = 0; i < kBands; ++i)
            shape[static_cast<size_t> (i)] = learnedShapeEnergy (routeIndex, i);

        // Same web lobe grammar: thresholded contiguous runs, <=2-band gap merge,
        // and discard one-band specks.
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

        auto baseHalfPan = [&] () -> float
        {
            if (track.spatialVoiceCount > 1)
                return 0.30f * 0.52f;
            const float webWidth = 0.35f + 2.35f * clamp01 (track.width);
            return 0.30f * (0.26f + 0.86f * (webWidth * 0.5f));
        };

        auto radiusForBand = [&] (int band, float swell) -> float
        {
            const float s = shape[static_cast<size_t> (band)];
            if (s <= kShapeGate)
                return 0.0f;
            for (const auto& lobe : lobes)
            {
                if (band < lobe.first || band > lobe.second)
                    continue;
                const int span = std::max (1, lobe.second - lobe.first);
                const float u = -1.0f + 2.0f * static_cast<float> (band - lobe.first) /
                    static_cast<float> (span);
                const float round = std::sqrt (std::max (0.0f, 1.0f - u * u * 0.94f));
                return baseHalfPan () * std::pow (s, 0.55f) * round * swell;
            }
            return 0.0f;
        };

        struct GdiPlusRuntime
        {
            ULONG_PTR token = 0;
            GdiPlusRuntime ()
            {
                Gdiplus::GdiplusStartupInput input;
                Gdiplus::GdiplusStartup (&token, &input, nullptr);
            }
            ~GdiPlusRuntime ()
            {
                if (token != 0) Gdiplus::GdiplusShutdown (token);
            }
        };
        static GdiPlusRuntime gdiplusRuntime;
        (void) gdiplusRuntime;

        Gdiplus::Graphics gg (dc);
        gg.SetCompositingMode (Gdiplus::CompositingModeSourceOver);
        gg.SetCompositingQuality (Gdiplus::CompositingQualityHighQuality);
        gg.SetSmoothingMode (Gdiplus::SmoothingModeAntiAlias);
        gg.SetPixelOffsetMode (Gdiplus::PixelOffsetModeHalf);

        const COLORREF raw = fieldRouteColor (*track.meta);
        auto gpColor = [&] (float alpha, COLORREF c) -> Gdiplus::Color
        {
            const int a = static_cast<int> (std::round (clamp01 (alpha) * 255.0f));
            return Gdiplus::Color (static_cast<BYTE> (std::clamp (a, 0, 255)),
                GetRValue (c), GetGValue (c), GetBValue (c));
        };

        constexpr int kRingSegments = 18;
        const float frontness = 1.0f - clamp01 ((track.visualZ - 0.08f) / 0.76f);
        const float depthGain = 0.50f + 0.85f * frontness;

        auto ringPoints = [&] (int band, float swell, bool floorRing)
        {
            std::array<Gdiplus::PointF, kRingSegments + 1> pts {};
            const float rx = radiusForBand (band, swell);
            const float rz = rx / 1.70f * (floorRing ? 1.0f : depthGain);
            const float wy = floorRing ? 0.0f : roomYForFrequency (
                bandHz[static_cast<size_t> (band)].load (std::memory_order_relaxed));
            for (int k = 0; k <= kRingSegments; ++k)
            {
                const float th = static_cast<float> (k) / static_cast<float> (kRingSegments) *
                    6.28318530718f;
                const auto p = projectWorld (
                    track.balance + rx * std::cos (th),
                    wy,
                    track.visualZ + rz * std::sin (th), area);
                pts[static_cast<size_t> (k)] = Gdiplus::PointF (
                    static_cast<Gdiplus::REAL> (p.x), static_cast<Gdiplus::REAL> (p.y));
            }
            return pts;
        };

        auto fillRing = [&] (int band, float swell, const Gdiplus::SolidBrush& brush, bool floorRing)
        {
            if (radiusForBand (band, swell) <= 0.0f)
                return;
            auto pts = ringPoints (band, swell, floorRing);
            Gdiplus::GraphicsPath path;
            path.AddPolygon (pts.data (), static_cast<INT> (pts.size ()));
            gg.FillPath (&brush, &path);
        };

        auto strokeRing = [&] (int band, float swell, Gdiplus::Pen& pen)
        {
            if (radiusForBand (band, swell) <= 0.0f)
                return;
            auto pts = ringPoints (band, swell, false);
            Gdiplus::GraphicsPath path;
            path.AddPolygon (pts.data (), static_cast<INT> (pts.size ()));
            gg.DrawPath (&pen, &path);
        };

        // Browser shadow: actual lobe footprint projected on the floor.
        const float shadowA = (0.05f + 0.28f * presence);
        Gdiplus::SolidBrush shadowBrush (gpColor (shadowA, RGB (3, 6, 12)));
        for (const auto& lobe : lobes)
        {
            int widestBand = lobe.first;
            float widest = 0.0f;
            for (int i = lobe.first; i <= lobe.second; ++i)
            {
                const float r = radiusForBand (i, 1.0f);
                if (r > widest) { widest = r; widestBand = i; }
            }
            if (widest > 0.0f)
                fillRing (widestBand, 1.0f, shadowBrush, true);
        }

        // Exact canvas opacity grammar. Real SourceOver alpha is the key difference
        // from V0.23-V0.31, which pre-mixed colours into the room background.
        const float bodyA = 0.012f + (0.020f + 0.030f * frontness) * presence;
        const float lineA = 0.10f + (0.24f + 0.55f * frontness) * presence;
        Gdiplus::SolidBrush bodyBrush (gpColor (bodyA, raw));
        for (const auto& lobe : lobes)
            for (int i = lobe.first; i <= lobe.second; ++i)
                fillRing (i, 1.0f, bodyBrush, false);

        // Sparse contour rings: every fourth band, not every band.
        Gdiplus::Pen contourPen (gpColor (lineA * 0.30f, raw), 0.70f);
        contourPen.SetLineJoin (Gdiplus::LineJoinRound);
        for (const auto& lobe : lobes)
            for (int i = lobe.first; i <= lobe.second; i += 4)
                strokeRing (i, 1.0f, contourPen);

        // One thin lobe silhouette, constructed the same way as browser lobePath().
        Gdiplus::Pen silhouettePen (gpColor (lineA, raw), 0.8f + frontness * 0.8f);
        silhouettePen.SetLineJoin (Gdiplus::LineJoinRound);
        for (const auto& lobe : lobes)
        {
            const int lo = std::max (0, lobe.first - 1);
            const int hi = std::min (kBands - 1, lobe.second + 1);
            std::vector<Gdiplus::PointF> outline;
            outline.reserve (static_cast<size_t> ((hi - lo + 1) * 2));
            for (int i = lo; i <= hi; ++i)
            {
                const float rx = (i < lobe.first || i > lobe.second) ? 0.0f : radiusForBand (i, 1.0f);
                const float wy = roomYForFrequency (bandHz[static_cast<size_t> (i)].load (std::memory_order_relaxed));
                const auto p = projectWorld (track.balance - rx, wy, track.visualZ, area);
                outline.emplace_back (static_cast<Gdiplus::REAL> (p.x), static_cast<Gdiplus::REAL> (p.y));
            }
            for (int i = hi; i >= lo; --i)
            {
                const float rx = (i < lobe.first || i > lobe.second) ? 0.0f : radiusForBand (i, 1.0f);
                const float wy = roomYForFrequency (bandHz[static_cast<size_t> (i)].load (std::memory_order_relaxed));
                const auto p = projectWorld (track.balance + rx, wy, track.visualZ, area);
                outline.emplace_back (static_cast<Gdiplus::REAL> (p.x), static_cast<Gdiplus::REAL> (p.y));
            }
            if (outline.size () >= 3)
            {
                Gdiplus::GraphicsPath path;
                path.AddLines (outline.data (), static_cast<INT> (outline.size ()));
                path.CloseFigure ();
                gg.DrawPath (&silhouettePen, &path);
            }
        }

        // Browser's small upper-left body light. It is a translucent ellipse, not
        // the opaque grey dot that was removed in V0.30.
        if (presence > 0.10f)
        {
            Gdiplus::SolidBrush hiBrush (gpColor (0.14f * presence * frontness, RGB (255, 255, 255)));
            for (const auto& lobe : lobes)
            {
                float minX = 1.0e9f, maxX = -1.0e9f, minY = 1.0e9f, maxY = -1.0e9f;
                for (int i = lobe.first; i <= lobe.second; ++i)
                {
                    const float rx = radiusForBand (i, 1.0f);
                    const float wy = roomYForFrequency (bandHz[static_cast<size_t> (i)].load (std::memory_order_relaxed));
                    const auto pl = projectWorld (track.balance - rx, wy, track.visualZ, area);
                    const auto pr = projectWorld (track.balance + rx, wy, track.visualZ, area);
                    minX = std::min (minX, static_cast<float> (std::min (pl.x, pr.x)));
                    maxX = std::max (maxX, static_cast<float> (std::max (pl.x, pr.x)));
                    minY = std::min (minY, static_cast<float> (std::min (pl.y, pr.y)));
                    maxY = std::max (maxY, static_cast<float> (std::max (pl.y, pr.y)));
                }
                if (maxX > minX + 8.0f && maxY > minY + 8.0f)
                {
                    const float rx = (maxX - minX) * 0.50f;
                    const float ry = (maxY - minY) * 0.50f;
                    const float cx = (minX + maxX) * 0.50f - rx * 0.30f;
                    const float cy = (minY + maxY) * 0.50f - ry * 0.42f;
                    gg.TranslateTransform (cx, cy);
                    gg.RotateTransform (-20.0535f);
                    gg.FillEllipse (&hiBrush, -rx * 0.24f, -ry * 0.13f,
                        rx * 0.48f, ry * 0.26f);
                    gg.ResetTransform ();
                }
            }
        }
    }
'''

replace_function(
    "    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)",
    web_renderer,
    "web spectral body renderer",
)

# Scene copy: explicitly describe this as renderer parity, not a DSP/analysis revision.
text = text.replace(
    "V0.31: sustained discrete L/R stays two stable bodies; transient L/R stays current-hit only",
    "V0.33 renderer parity: GDI+ real alpha/AA + browser stacked rings/contours/silhouette"
)

out.write_text(text, encoding="utf-8")
print(out)
