from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v010_dir = root / "fl-native-visualizer-v010"

runpy.run_path(str(v010_dir / "generate_v010.py"), run_name="__main__")
src = v010_dir / "generated" / "fieldv010.cpp"
out = here / "generated" / "fieldv011.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.11 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.11 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.11 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


# Fresh plugin identity.
text = text.replace("Field V0.10 3D Orbit Visualizer", "Field V0.11 Room Space Visualizer")
text = text.replace("FieldV010", "FieldV011")
text = text.replace("V0.10", "V0.11")
text = text.replace("V010", "V011")

# The web prototype opens at a slight three-quarter room angle.
text = text.replace("self->orbitYaw = 0.0f;\n                    self->orbitPitch = 0.0f;",
                    "self->orbitYaw = 0.40f;\n                    self->orbitPitch = 0.17f;")
text = text.replace("float orbitYaw = 0.34f;\n    float orbitPitch = -0.10f;",
                    "float orbitYaw = 0.40f;\n    float orbitPitch = 0.17f;")

replace_once(
    "    float visualZ = 0.0f;\n};",
    "    float visualZ = 0.08f;\n    float volumeThickness = 0.08f;\n};",
    "3D volume fields",
)

# Port the web app's room-space camera language: x=pan, y=frequency, z=front/back.
room_projection = r'''    struct ProjectedPoint
    {
        int x = 0;
        int y = 0;
        float depth = 0.0f;
        float scale = 1.0f;
    };

    float roomYForFrequency (float hz) const
    {
        constexpr float minHz = 70.0f;
        constexpr float maxHz = 16000.0f;
        const float t = clamp01 ((std::log (std::max (hz, minHz)) - std::log (minHz)) /
                                 (std::log (maxHz) - std::log (minHz)));
        return 0.06f + t * 0.96f;
    }

    ProjectedPoint projectWorld (float wx, float wy, float z01, const RECT& area) const
    {
        // Same coordinate model as the browser prototype.
        constexpr float focal = 2.40f;
        constexpr float cameraDistance = 2.65f;
        constexpr float eyeY = 0.46f;
        constexpr float zSpan = 1.70f;

        const float X = wx;
        const float Y = wy - eyeY;
        const float Z = (z01 - 0.5f) * zSpan;

        const float cy = std::cos (orbitYaw);
        const float sy = std::sin (orbitYaw);
        const float x1 = X * cy + Z * sy;
        const float z1 = -X * sy + Z * cy;

        const float cp = std::cos (orbitPitch);
        const float sp = std::sin (orbitPitch);
        const float y1 = Y * cp - z1 * sp;
        const float z2 = Y * sp + z1 * cp;

        const float d = std::max (0.35f, cameraDistance + z2);
        const float s = focal / d;
        const float w = static_cast<float> (area.right - area.left);
        const float h = static_cast<float> (area.bottom - area.top);
        const float cx = static_cast<float> (area.left + area.right) * 0.5f;
        const float horizon = static_cast<float> (area.top) + h * 0.50f;
        const float halfW = w * 0.46f * orbitZoom;
        const float halfH = h * 0.62f * orbitZoom;

        ProjectedPoint p;
        p.x = static_cast<int> (std::lround (cx + x1 * halfW * s));
        p.y = static_cast<int> (std::lround (horizon - y1 * halfH * s));
        p.depth = d;
        p.scale = s;
        return p;
    }

    float cameraDepthForTrack (const DrawTrack& track) const
    {
        return projectWorld (track.balance, 0.50f, track.visualZ, RECT {0, 0, 1000, 700}).depth;
    }

    std::array<POINT, kBands * 2> projectedBodyPointsAtDepth (
        const DrawTrack& track, const RECT& area, float z,
        float expansionWorld = 0.0f, float xOffsetWorld = 0.0f) const
    {
        std::array<POINT, kBands * 2> points {};
        if (!track.meta)
            return points;
        const int route = track.meta->routeIndex;
        if (route < 1 || route > kMaxRoutes)
            return points;
        const size_t routeIndex = static_cast<size_t> (route - 1);

        for (int band = 0; band < kBands; ++band)
        {
            const float energy = routeSpectrum[routeIndex][static_cast<size_t> (band)].load (std::memory_order_relaxed);
            const float hz = bandHz[static_cast<size_t> (band)].load (std::memory_order_relaxed);
            const float y = roomYForFrequency (hz);
            const float halfWidth = 0.012f + energy * (0.055f + track.width * 0.090f) + expansionWorld;
            const auto left = projectWorld (track.balance + xOffsetWorld - halfWidth, y, z, area);
            const auto right = projectWorld (track.balance + xOffsetWorld + halfWidth, y, z, area);
            points[static_cast<size_t> (band)] = {left.x, left.y};
            points[static_cast<size_t> (kBands * 2 - 1 - band)] = {right.x, right.y};
        }
        return points;
    }

    std::array<POINT, kBands * 2> projectedBodyPoints (
        const DrawTrack& track, const RECT& area, float expansionPx = 0.0f, float xOffsetPx = 0.0f) const
    {
        const float worldPerPixel = 2.0f / std::max (240.0f, static_cast<float> (area.right - area.left));
        return projectedBodyPointsAtDepth (
            track, area, track.visualZ, expansionPx * worldPerPixel, xOffsetPx * worldPerPixel);
    }

    void fillQuad (HDC dc, const std::array<POINT, 4>& q, COLORREF color) const
    {
        HBRUSH brush = CreateSolidBrush (color);
        auto oldBrush = SelectObject (dc, brush);
        auto oldPen = SelectObject (dc, GetStockObject (NULL_PEN));
        Polygon (dc, q.data (), 4);
        SelectObject (dc, oldPen);
        SelectObject (dc, oldBrush);
        DeleteObject (brush);
    }

    void drawRoom (HDC dc, const RECT& area)
    {
        const COLORREF bg = RGB (16, 20, 26);
        const auto p000 = projectWorld (-1.0f, 0.04f, 0.0f, area);
        const auto p100 = projectWorld ( 1.0f, 0.04f, 0.0f, area);
        const auto p001 = projectWorld (-1.0f, 0.04f, 1.0f, area);
        const auto p101 = projectWorld ( 1.0f, 0.04f, 1.0f, area);
        const auto p011 = projectWorld (-1.0f, 1.02f, 1.0f, area);
        const auto p111 = projectWorld ( 1.0f, 1.02f, 1.0f, area);
        const auto p010 = projectWorld (-1.0f, 1.02f, 0.0f, area);
        const auto p110 = projectWorld ( 1.0f, 1.02f, 0.0f, area);

        fillQuad (dc, {{{p000.x,p000.y},{p100.x,p100.y},{p101.x,p101.y},{p001.x,p001.y}}},
                  mixColor (RGB (25, 36, 52), bg, 0.18f));
        fillQuad (dc, {{{p001.x,p001.y},{p101.x,p101.y},{p111.x,p111.y},{p011.x,p011.y}}},
                  mixColor (RGB (18, 30, 48), bg, 0.12f));
        fillQuad (dc, {{{p000.x,p000.y},{p001.x,p001.y},{p011.x,p011.y},{p010.x,p010.y}}},
                  mixColor (RGB (17, 26, 40), bg, 0.24f));
        fillQuad (dc, {{{p100.x,p100.y},{p110.x,p110.y},{p111.x,p111.y},{p101.x,p101.y}}},
                  mixColor (RGB (17, 26, 40), bg, 0.24f));

        HPEN gridPen = CreatePen (PS_SOLID, 1, RGB (45, 58, 76));
        auto oldPen = SelectObject (dc, gridPen);

        // Floor perspective rungs and pan lanes.
        for (int k = 0; k <= 8; ++k)
        {
            const float z = static_cast<float> (k) / 8.0f;
            const auto a = projectWorld (-1.0f, 0.04f, z, area);
            const auto b = projectWorld ( 1.0f, 0.04f, z, area);
            MoveToEx (dc, a.x, a.y, nullptr); LineTo (dc, b.x, b.y);
        }
        for (float x : std::array<float, 5> {-1.0f, -0.5f, 0.0f, 0.5f, 1.0f})
        {
            const auto a = projectWorld (x, 0.04f, 0.0f, area);
            const auto b = projectWorld (x, 0.04f, 1.0f, area);
            MoveToEx (dc, a.x, a.y, nullptr); LineTo (dc, b.x, b.y);
        }

        // Frequency shelves run through the room, matching the browser app.
        const std::array<float, 9> labels {
            70.0f, 120.0f, 250.0f, 500.0f, 1000.0f, 2000.0f, 5000.0f, 10000.0f, 16000.0f
        };
        for (float hz : labels)
        {
            const float y = roomYForFrequency (hz);
            const auto bl = projectWorld (-1.0f, y, 1.0f, area);
            const auto br = projectWorld ( 1.0f, y, 1.0f, area);
            const auto fl = projectWorld (-1.0f, y, 0.0f, area);
            MoveToEx (dc, bl.x, bl.y, nullptr); LineTo (dc, br.x, br.y);
            MoveToEx (dc, fl.x, fl.y, nullptr); LineTo (dc, bl.x, bl.y);
        }

        // Room edges.
        HPEN edgePen = CreatePen (PS_SOLID, 1, RGB (74, 92, 115));
        SelectObject (dc, edgePen);
        const std::array<std::pair<ProjectedPoint,ProjectedPoint>, 8> edges {{
            {p000,p100},{p001,p101},{p011,p111},{p000,p010},
            {p100,p110},{p001,p011},{p101,p111},{p010,p011}
        }};
        for (const auto& e : edges)
        {
            MoveToEx (dc, e.first.x, e.first.y, nullptr); LineTo (dc, e.second.x, e.second.y);
        }
        SelectObject (dc, oldPen);
        DeleteObject (edgePen);
        DeleteObject (gridPen);

        SetBkMode (dc, TRANSPARENT);
        SetTextColor (dc, RGB (103, 121, 143));
        for (float hz : labels)
        {
            wchar_t label[32] {};
            if (hz >= 1000.0f) swprintf_s (label, L"%.0fk", hz / 1000.0f);
            else swprintf_s (label, L"%.0f", hz);
            const auto p = projectWorld (-1.0f, roomYForFrequency (hz), 1.0f, area);
            RECT fr {p.x - 45, p.y - 10, p.x - 4, p.y + 10};
            DrawTextW (dc, label, -1, &fr, DT_RIGHT | DT_SINGLELINE | DT_VCENTER);
        }

        // Simple front monitors, as orientation anchors like the web room.
        for (float side : std::array<float, 2> {-1.0f, 1.0f})
        {
            const float x0 = side * 0.88f;
            const auto a = projectWorld (x0 - 0.07f, 0.18f, 0.03f, area);
            const auto b = projectWorld (x0 + 0.07f, 0.18f, 0.03f, area);
            const auto c = projectWorld (x0 + 0.07f, 0.38f, 0.03f, area);
            const auto d = projectWorld (x0 - 0.07f, 0.38f, 0.03f, area);
            fillQuad (dc, {{{a.x,a.y},{b.x,b.y},{c.x,c.y},{d.x,d.y}}}, RGB (29, 37, 48));
            HPEN sp = CreatePen (PS_SOLID, 1, RGB (104, 123, 144));
            auto op = SelectObject (dc, sp);
            Ellipse (dc, (a.x+b.x)/2-5, (a.y+d.y)/2-5, (a.x+b.x)/2+5, (a.y+d.y)/2+5);
            SelectObject (dc, op); DeleteObject (sp);
        }

        RECT hint {area.left + 12, area.top + 8, area.right - 12, area.top + 30};
        SetTextColor (dc, RGB (98, 117, 139));
        DrawTextW (dc, L"X PAN   |   Y FREQUENCY   |   Z APPARENT DEPTH     DRAG ORBIT / WHEEL ZOOM / DOUBLE-CLICK RESET", -1,
                   &hint, DT_RIGHT | DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);
    }

    void drawFieldGrid (HDC dc, const RECT& area)
    {
        drawRoom (dc, area);
    }

'''
replace_between(
    "    struct ProjectedPoint\n    {",
    "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)",
    room_projection,
    "web room projection",
)

# Make FX layers inhabit the same room volume instead of being a flat overlay.
room_fx = r'''    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)
    {
        if (!track.meta || (reverbAmount <= 0.004f && delayAmount <= 0.004f))
            return;

        COLORREF raw = static_cast<COLORREF> (track.meta->color & 0x00FFFFFF);
        if (raw == RGB (0, 0, 0)) raw = RGB (115, 160, 190);
        const COLORREF bg = RGB (16, 20, 26);

        auto outlineAt = [&] (float z, float expansion, float xOffset, float fade)
        {
            const auto points = projectedBodyPointsAtDepth (track, area, std::clamp (z, 0.01f, 0.99f), expansion, xOffset);
            HPEN pen = CreatePen (PS_SOLID, 1, mixColor (raw, bg, fade));
            auto oldPen = SelectObject (dc, pen);
            auto oldBrush = SelectObject (dc, GetStockObject (NULL_BRUSH));
            Polygon (dc, points.data (), static_cast<int> (points.size ()));
            SelectObject (dc, oldBrush); SelectObject (dc, oldPen); DeleteObject (pen);
        };

        if (reverbAmount > 0.004f)
        {
            const float zSpread = 0.035f + reverbAmount * 0.16f;
            outlineAt (track.visualZ + zSpread, 0.018f + reverbAmount * 0.055f, 0.0f, 0.78f);
            outlineAt (track.visualZ + zSpread * 1.8f, 0.030f + reverbAmount * 0.075f, 0.0f, 0.88f);
            outlineAt (track.visualZ - zSpread * 0.45f, 0.012f + reverbAmount * 0.040f, 0.0f, 0.84f);
        }
        if (delayAmount > 0.004f)
        {
            const float side = 0.035f + delayAmount * 0.12f;
            const float back = 0.025f + delayAmount * 0.10f;
            outlineAt (track.visualZ + back, 0.008f, -side, 0.82f);
            outlineAt (track.visualZ + back * 1.7f, 0.006f, side, 0.89f);
        }
    }

'''
replace_between(
    "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)\n    {",
    "    void fxAmountsForSource",
    room_fx,
    "3D room FX aura",
)

# Replace the 2D polygon body with a real extruded 3D spectral volume.
volume_body = r'''    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)
    {
        if (!track.meta)
            return;
        const int route = track.meta->routeIndex;
        if (route < 1 || route > kMaxRoutes)
            return;

        const float halfDepth = std::clamp (track.volumeThickness * 0.5f, 0.018f, 0.10f);
        const float zFront = std::clamp (track.visualZ - halfDepth, 0.01f, 0.98f);
        const float zBack  = std::clamp (track.visualZ + halfDepth, 0.02f, 0.99f);
        const auto front = projectedBodyPointsAtDepth (track, area, zFront);
        const auto back  = projectedBodyPointsAtDepth (track, area, zBack);

        COLORREF raw = static_cast<COLORREF> (track.meta->color & 0x00FFFFFF);
        if (raw == RGB (0, 0, 0)) raw = RGB (115, 160, 190);
        const COLORREF bg = RGB (16, 20, 26);
        const COLORREF frontFill = mixColor (raw, bg, 0.58f);
        const COLORREF backFill = mixColor (raw, bg, 0.78f);
        const COLORREF sideFill = mixColor (raw, bg, 0.70f);
        const COLORREF outline = mixColor (raw, RGB (242, 248, 255), 0.22f);

        HBRUSH backBrush = CreateSolidBrush (backFill);
        HPEN backPen = CreatePen (PS_SOLID, 1, mixColor (outline, bg, 0.42f));
        auto oldBrush = SelectObject (dc, backBrush);
        auto oldPen = SelectObject (dc, backPen);
        Polygon (dc, back.data (), static_cast<int> (back.size ()));
        SelectObject (dc, oldPen); SelectObject (dc, oldBrush);
        DeleteObject (backPen); DeleteObject (backBrush);

        // One curved side is enough to make the spectral silhouette read as a volume.
        const bool rightSideVisible = std::sin (orbitYaw) >= 0.0f;
        HBRUSH sideBrush = CreateSolidBrush (sideFill);
        HPEN sidePen = CreatePen (PS_SOLID, 1, mixColor (outline, bg, 0.32f));
        oldBrush = SelectObject (dc, sideBrush);
        oldPen = SelectObject (dc, sidePen);
        for (int band = 0; band < kBands - 1; ++band)
        {
            int i0, i1;
            if (rightSideVisible)
            {
                i0 = kBands * 2 - 1 - band;
                i1 = kBands * 2 - 2 - band;
            }
            else
            {
                i0 = band;
                i1 = band + 1;
            }
            std::array<POINT, 4> q {{front[static_cast<size_t> (i0)], front[static_cast<size_t> (i1)],
                                      back[static_cast<size_t> (i1)], back[static_cast<size_t> (i0)]}};
            Polygon (dc, q.data (), 4);
        }
        SelectObject (dc, oldPen); SelectObject (dc, oldBrush);
        DeleteObject (sidePen); DeleteObject (sideBrush);

        // Top/bottom caps.
        const int rTop = kBands * 2 - 1;
        const int rBottom = kBands;
        fillQuad (dc, {{{front[0].x,front[0].y},{front[rTop].x,front[rTop].y},
                        {back[rTop].x,back[rTop].y},{back[0].x,back[0].y}}}, sideFill);
        fillQuad (dc, {{{front[kBands-1].x,front[kBands-1].y},{front[rBottom].x,front[rBottom].y},
                        {back[rBottom].x,back[rBottom].y},{back[kBands-1].x,back[kBands-1].y}}}, sideFill);

        HBRUSH frontBrush = CreateSolidBrush (frontFill);
        HPEN frontPen = CreatePen (PS_SOLID, 2, outline);
        oldBrush = SelectObject (dc, frontBrush);
        oldPen = SelectObject (dc, frontPen);
        Polygon (dc, front.data (), static_cast<int> (front.size ()));
        SelectObject (dc, oldPen); SelectObject (dc, oldBrush);
        DeleteObject (frontPen); DeleteObject (frontBrush);

        // Depth spine joins the front and back centres.
        const float midY = 0.50f;
        const auto a = projectWorld (track.balance, midY, zFront, area);
        const auto b = projectWorld (track.balance, midY, zBack, area);
        HPEN spine = CreatePen (PS_SOLID, 1, mixColor (outline, bg, 0.18f));
        oldPen = SelectObject (dc, spine);
        MoveToEx (dc, a.x, a.y, nullptr); LineTo (dc, b.x, b.y);
        SelectObject (dc, oldPen); DeleteObject (spine);
    }

'''
replace_between(
    "    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)\n    {",
    "    void paint (HWND hwnd)",
    volume_body,
    "extruded spectral volume",
)

# Replace arbitrary mixer-order Z spacing with apparent acoustic placement.
old_depth = '''        const int depthCount = static_cast<int> (active.size ());
        const float depthSpan = depthCount <= 1 ? 0.0f :
            std::min (2.80f, 0.18f * static_cast<float> (depthCount - 1));
        for (int i = 0; i < depthCount; ++i)
        {
            const float t = depthCount <= 1 ? 0.0f :
                static_cast<float> (i) / static_cast<float> (depthCount - 1) - 0.5f;
            active[static_cast<size_t> (i)].visualZ = t * depthSpan;
        }
'''
new_depth = '''        // Actual room placement from the signal we can observe: X is measured stereo balance.
        // Z is apparent acoustic depth: temporal wetness is the strongest cue, with level and
        // stereo diffuseness as smaller cues. This is an inferred perceptual distance, not a DAW
        // routing index and never changes the audio in this visualizer build.
        for (auto& track : active)
        {
            if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
                continue;
            float reverbAmount = 0.0f, delayAmount = 0.0f;
            fxAmountsForSource (track.meta->routeIndex, reverbAmount, delayAmount);
            const size_t idx = static_cast<size_t> (track.meta->routeIndex - 1);
            const float levelDistance = clamp01 ((-track.peakDb - 8.0f) / 48.0f);
            const float temporalWet = clamp01 (reverbAmount * 0.92f + delayAmount * 0.30f);
            const float diffuse = clamp01 (track.width * 0.75f);
            const float targetDepth = std::clamp (
                0.06f + temporalWet * 0.62f + levelDistance * 0.25f + diffuse * 0.07f,
                0.04f, 0.94f);
            float& smoothDepth = spatialDepth[idx];
            if (smoothDepth <= 0.001f)
                smoothDepth = targetDepth;
            else
                smoothDepth += (targetDepth - smoothDepth) * 0.045f;
            track.visualZ = smoothDepth;
            track.volumeThickness = std::clamp (
                0.045f + (1.0f - levelDistance) * 0.055f + track.width * 0.030f,
                0.040f, 0.145f);
        }
'''
replace_once(old_depth, new_depth, "apparent acoustic depth")

# Add persistent per-route depth smoothing.
replace_once(
    "    float orbitZoom = 1.0f;\n",
    "    float orbitZoom = 1.0f;\n    std::array<float, kMaxRoutes> spatialDepth {};\n",
    "depth smoothing state",
)

# Update UI copy from generic 3D layering to the actual room model.
text = text.replace(
    "3D orbit view. Z is view-only mixer-order separation; audio/pan/FX remain unchanged.",
    "Room view from the mix position. X=pan, Y=frequency, Z=apparent acoustic depth; objects are true extruded spectral volumes."
)
text = text.replace(
    "DRAG TO ORBIT   |   WHEEL TO ZOOM   |   DOUBLE-CLICK FOR FRONT VIEW",
    "DRAG TO ORBIT   |   WHEEL TO ZOOM   |   DOUBLE-CLICK TO RESET ROOM"
)

out.write_text(text, encoding="utf-8")
print(out)
