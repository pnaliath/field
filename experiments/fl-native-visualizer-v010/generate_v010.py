from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v009_dir = root / "fl-native-visualizer-v009"

runpy.run_path(str(v009_dir / "generate_v009.py"), run_name="__main__")
src = v009_dir / "generated" / "fieldv009.cpp"
out = here / "generated" / "fieldv010.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.10 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.10 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.10 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


# Fresh FL-native identity.
text = text.replace("Field V0.09 Recovering FX Visualizer", "Field V0.10 3D Orbit Visualizer")
text = text.replace("FieldV009", "FieldV010")
text = text.replace("V0.09", "V0.10")
text = text.replace("V009", "V010")

# Each spectral body gets a deterministic view-only Z coordinate. It does not alter audio.
replace_once(
    "    float width = 0.0f;\n};",
    "    float width = 0.0f;\n    float visualZ = 0.0f;\n};",
    "DrawTrack visual Z",
)

# Mouse orbit controls. Buttons still use normal click handling in the top strip.
old_switch = '''        switch (message)\n        {\n            case WM_LBUTTONUP:\n                self->handleClick (\n                    static_cast<int> (static_cast<short> (LOWORD (lParam))),\n                    static_cast<int> (static_cast<short> (HIWORD (lParam))));\n                return 0;\n            case WM_PAINT:\n                self->paint (hwnd);\n                return 0;\n            case WM_ERASEBKGND:\n                return 1;\n            default:\n                return DefWindowProcW (hwnd, message, wParam, lParam);\n        }'''
new_switch = '''        switch (message)\n        {\n            case WM_LBUTTONDOWN:\n            {\n                const int x = static_cast<int> (static_cast<short> (LOWORD (lParam)));\n                const int y = static_cast<int> (static_cast<short> (HIWORD (lParam)));\n                if (x >= 235 && y >= 112)\n                {\n                    self->orbitDragging = true;\n                    self->orbitLast = {x, y};\n                    SetCapture (hwnd);\n                    return 0;\n                }\n                break;\n            }\n            case WM_MOUSEMOVE:\n                if (self->orbitDragging && (wParam & MK_LBUTTON) != 0)\n                {\n                    const int x = static_cast<int> (static_cast<short> (LOWORD (lParam)));\n                    const int y = static_cast<int> (static_cast<short> (HIWORD (lParam)));\n                    const int dx = x - self->orbitLast.x;\n                    const int dy = y - self->orbitLast.y;\n                    self->orbitYaw += static_cast<float> (dx) * 0.0080f;\n                    self->orbitPitch = std::clamp (self->orbitPitch + static_cast<float> (dy) * 0.0060f, -1.10f, 1.10f);\n                    self->orbitLast = {x, y};\n                    InvalidateRect (hwnd, nullptr, FALSE);\n                    return 0;\n                }\n                break;\n            case WM_LBUTTONUP:\n                if (self->orbitDragging)\n                {\n                    self->orbitDragging = false;\n                    if (GetCapture () == hwnd)\n                        ReleaseCapture ();\n                    return 0;\n                }\n                self->handleClick (\n                    static_cast<int> (static_cast<short> (LOWORD (lParam))),\n                    static_cast<int> (static_cast<short> (HIWORD (lParam))));\n                return 0;\n            case WM_LBUTTONDBLCLK:\n            {\n                const int x = static_cast<int> (static_cast<short> (LOWORD (lParam)));\n                const int y = static_cast<int> (static_cast<short> (HIWORD (lParam)));\n                if (x >= 235 && y >= 112)\n                {\n                    self->orbitYaw = 0.0f;\n                    self->orbitPitch = 0.0f;\n                    self->orbitZoom = 1.0f;\n                    InvalidateRect (hwnd, nullptr, FALSE);\n                    return 0;\n                }\n                break;\n            }\n            case WM_MOUSEWHEEL:\n            {\n                const int delta = GET_WHEEL_DELTA_WPARAM (wParam);\n                const float steps = static_cast<float> (delta) / static_cast<float> (WHEEL_DELTA);\n                self->orbitZoom = std::clamp (self->orbitZoom * std::pow (1.10f, steps), 0.55f, 2.25f);\n                InvalidateRect (hwnd, nullptr, FALSE);\n                return 0;\n            }\n            case WM_PAINT:\n                self->paint (hwnd);\n                return 0;\n            case WM_ERASEBKGND:\n                return 1;\n            default:\n                return DefWindowProcW (hwnd, message, wParam, lParam);\n        }\n        return DefWindowProcW (hwnd, message, wParam, lParam);'''
replace_once(old_switch, new_switch, "orbit window events")
text = text.replace("wc.style = CS_HREDRAW | CS_VREDRAW;", "wc.style = CS_HREDRAW | CS_VREDRAW | CS_DBLCLKS;")

# Replace the flat field grid and body projection with a shared 3D camera projection.
projection_and_grid = r'''    struct ProjectedPoint
    {
        int x = 0;
        int y = 0;
        float depth = 0.0f;
    };

    float normalizedFrequencyY (float hz) const
    {
        const float minHz = 70.0f;
        const float maxHz = 16000.0f;
        const float t = clamp01 ((std::log (std::max (hz, minHz)) - std::log (minHz)) /
                                 (std::log (maxHz) - std::log (minHz)));
        return t * 2.0f - 1.0f;
    }

    ProjectedPoint projectWorld (float x, float y, float z, const RECT& area) const
    {
        const float cosYaw = std::cos (orbitYaw);
        const float sinYaw = std::sin (orbitYaw);
        const float x1 = x * cosYaw + z * sinYaw;
        const float z1 = -x * sinYaw + z * cosYaw;

        const float cosPitch = std::cos (orbitPitch);
        const float sinPitch = std::sin (orbitPitch);
        const float y1 = y * cosPitch - z1 * sinPitch;
        const float z2 = y * sinPitch + z1 * cosPitch;

        constexpr float cameraDistance = 5.2f;
        const float perspective = std::clamp (cameraDistance / std::max (1.8f, cameraDistance + z2), 0.48f, 2.40f) * orbitZoom;
        const float halfW = static_cast<float> (area.right - area.left) * 0.40f;
        const float halfH = static_cast<float> (area.bottom - area.top) * 0.47f;
        const float cx = static_cast<float> (area.left + area.right) * 0.5f;
        const float cy = static_cast<float> (area.top + area.bottom) * 0.5f;

        ProjectedPoint p;
        p.x = static_cast<int> (std::lround (cx + x1 * halfW * perspective));
        p.y = static_cast<int> (std::lround (cy - y1 * halfH * perspective));
        p.depth = z2;
        return p;
    }

    float cameraDepthForTrack (const DrawTrack& track) const
    {
        const float cosYaw = std::cos (orbitYaw);
        const float sinYaw = std::sin (orbitYaw);
        const float z1 = -track.balance * sinYaw + track.visualZ * cosYaw;
        return z1 * std::cos (orbitPitch);
    }

    std::array<POINT, kBands * 2> projectedBodyPoints (
        const DrawTrack& track, const RECT& area, float expansionPx = 0.0f, float xOffsetPx = 0.0f) const
    {
        std::array<POINT, kBands * 2> points {};
        if (!track.meta)
            return points;
        const int route = track.meta->routeIndex;
        if (route < 1 || route > kMaxRoutes)
            return points;
        const size_t routeIndex = static_cast<size_t> (route - 1);
        const float halfWScale = std::max (1.0f, static_cast<float> (area.right - area.left) * 0.40f);
        const float xOffsetWorld = xOffsetPx / halfWScale;

        for (int band = 0; band < kBands; ++band)
        {
            const float energy = routeSpectrum[routeIndex][static_cast<size_t> (band)].load (std::memory_order_relaxed);
            const float hz = bandHz[static_cast<size_t> (band)].load (std::memory_order_relaxed);
            const float y = normalizedFrequencyY (hz);
            const float halfWidthPx = 5.0f + energy * (24.0f + track.width * 42.0f) + expansionPx;
            const float halfWidthWorld = halfWidthPx / halfWScale;
            const auto left = projectWorld (track.balance + xOffsetWorld - halfWidthWorld, y, track.visualZ, area);
            const auto right = projectWorld (track.balance + xOffsetWorld + halfWidthWorld, y, track.visualZ, area);
            points[static_cast<size_t> (band)] = {left.x, left.y};
            points[static_cast<size_t> (kBands * 2 - 1 - band)] = {right.x, right.y};
        }
        return points;
    }

    void drawFieldGrid (HDC dc, const RECT& area)
    {
        HPEN gridPen = CreatePen (PS_SOLID, 1, RGB (36, 44, 54));
        auto oldPen = SelectObject (dc, gridPen);

        const std::array<float, 5> xs {-1.0f, -0.5f, 0.0f, 0.5f, 1.0f};
        const std::array<float, 3> zs {-1.35f, 0.0f, 1.35f};
        for (float z : zs)
        {
            for (float x : xs)
            {
                const auto a = projectWorld (x, -1.0f, z, area);
                const auto b = projectWorld (x, 1.0f, z, area);
                MoveToEx (dc, a.x, a.y, nullptr);
                LineTo (dc, b.x, b.y);
            }
        }

        const std::array<float, 9> labels {
            70.0f, 120.0f, 250.0f, 500.0f, 1000.0f, 2000.0f, 5000.0f, 10000.0f, 16000.0f
        };
        for (float hz : labels)
        {
            const float y = normalizedFrequencyY (hz);
            const auto a = projectWorld (-1.0f, y, 0.0f, area);
            const auto b = projectWorld (1.0f, y, 0.0f, area);
            MoveToEx (dc, a.x, a.y, nullptr);
            LineTo (dc, b.x, b.y);
        }

        for (float x : std::array<float, 3> {-1.0f, 0.0f, 1.0f})
        {
            for (float y : std::array<float, 2> {-1.0f, 1.0f})
            {
                const auto a = projectWorld (x, y, -1.35f, area);
                const auto b = projectWorld (x, y, 1.35f, area);
                MoveToEx (dc, a.x, a.y, nullptr);
                LineTo (dc, b.x, b.y);
            }
        }

        SelectObject (dc, oldPen);
        DeleteObject (gridPen);
        SetTextColor (dc, RGB (93, 108, 124));
        SetBkMode (dc, TRANSPARENT);

        RECT hint {area.left + 8, area.top + 6, area.right - 8, area.top + 28};
        DrawTextW (dc, L"DRAG TO ORBIT   |   WHEEL TO ZOOM   |   DOUBLE-CLICK FOR FRONT VIEW", -1,
                   &hint, DT_RIGHT | DT_SINGLELINE | DT_VCENTER);

        for (float hz : labels)
        {
            wchar_t label[32] {};
            if (hz >= 1000.0f)
                swprintf_s (label, L"%.0fk", hz / 1000.0f);
            else
                swprintf_s (label, L"%.0f", hz);
            const auto p = projectWorld (-1.05f, normalizedFrequencyY (hz), 0.0f, area);
            RECT fr {p.x - 46, p.y - 10, p.x - 5, p.y + 10};
            DrawTextW (dc, label, -1, &fr, DT_RIGHT | DT_SINGLELINE | DT_VCENTER);
        }
    }

'''
replace_between(
    "    void drawFieldGrid (HDC dc, const RECT& area)\n    {",
    "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)",
    projection_and_grid,
    "3D projection/grid",
)

# Re-project attached FX layers into the same 3D plane as their source object.
fx_aura = r'''    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)
    {
        if (!track.meta || (reverbAmount <= 0.004f && delayAmount <= 0.004f))
            return;

        COLORREF raw = static_cast<COLORREF> (track.meta->color & 0x00FFFFFF);
        if (raw == RGB (0, 0, 0))
            raw = RGB (115, 160, 190);
        const COLORREF bg = RGB (16, 20, 26);

        auto drawLayer = [&] (float expansion, float xOffset, float fade, bool fillIt)
        {
            const auto points = projectedBodyPoints (track, area, expansion, xOffset);
            const COLORREF c = mixColor (raw, bg, fade);
            HPEN pen = CreatePen (PS_SOLID, 1, c);
            HBRUSH brush = fillIt ? CreateSolidBrush (mixColor (raw, bg, std::min (0.96f, fade + 0.08f))) :
                                   static_cast<HBRUSH> (GetStockObject (NULL_BRUSH));
            auto oldPen = SelectObject (dc, pen);
            auto oldBrush = SelectObject (dc, brush);
            Polygon (dc, points.data (), static_cast<int> (points.size ()));
            SelectObject (dc, oldBrush);
            SelectObject (dc, oldPen);
            DeleteObject (pen);
            if (fillIt)
                DeleteObject (brush);
        };

        if (reverbAmount > 0.004f)
        {
            drawLayer (10.0f + reverbAmount * 34.0f, 0.0f, 0.93f, true);
            drawLayer (6.0f + reverbAmount * 23.0f, 0.0f, 0.86f, false);
            drawLayer (3.0f + reverbAmount * 13.0f, 0.0f, 0.78f, false);
        }

        if (delayAmount > 0.004f)
        {
            const float spread = 9.0f + delayAmount * 18.0f;
            drawLayer (2.0f + delayAmount * 6.0f, -spread * 2.0f, 0.95f, false);
            drawLayer (2.0f + delayAmount * 5.0f, spread * 2.0f, 0.92f, false);
            drawLayer (1.0f + delayAmount * 3.0f, spread, 0.84f, false);
        }
    }

'''
replace_between(
    "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)\n    {",
    "    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)",
    fx_aura,
    "3D FX aura",
)

spectral_body = r'''    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)
    {
        if (!track.meta)
            return;
        const auto points = projectedBodyPoints (track, area);

        COLORREF raw = static_cast<COLORREF> (track.meta->color & 0x00FFFFFF);
        if (raw == RGB (0, 0, 0))
            raw = RGB (115, 160, 190);
        const COLORREF bg = RGB (16, 20, 26);
        const float depthShade = clamp01 ((cameraDepthForTrack (track) + 1.8f) / 3.6f);
        const COLORREF fill = mixColor (raw, bg, 0.62f + depthShade * 0.12f);
        const COLORREF outline = mixColor (raw, RGB (245, 250, 255), 0.18f);
        HBRUSH bodyBrush = CreateSolidBrush (fill);
        HPEN bodyPen = CreatePen (PS_SOLID, 2, outline);
        auto oldBrush = SelectObject (dc, bodyBrush);
        auto oldPen = SelectObject (dc, bodyPen);
        Polygon (dc, points.data (), static_cast<int> (points.size ()));
        SelectObject (dc, oldPen);
        SelectObject (dc, oldBrush);
        DeleteObject (bodyPen);
        DeleteObject (bodyBrush);

        const auto bottom = projectWorld (track.balance, -1.0f, track.visualZ, area);
        const auto top = projectWorld (track.balance, 1.0f, track.visualZ, area);
        HPEN spinePen = CreatePen (PS_SOLID, 1, mixColor (outline, bg, 0.25f));
        oldPen = SelectObject (dc, spinePen);
        MoveToEx (dc, bottom.x, bottom.y, nullptr);
        LineTo (dc, top.x, top.y);
        SelectObject (dc, oldPen);
        DeleteObject (spinePen);
    }

'''
replace_between(
    "    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)\n    {",
    "    void paint (HWND hwnd)",
    spectral_body,
    "3D spectral body",
)

# Stable mixer order supplies stable visual-only depth layers; render back-to-front for correct occlusion.
old_draw = '''        std::sort (active.begin (), active.end (), [] (const DrawTrack& a, const DrawTrack& b)\n        {\n            if (!a.meta || !b.meta) return a.meta != nullptr;\n            return a.meta->mixerIndex < b.meta->mixerIndex;\n        });\n        for (const auto& track : active)\n        {\n            float reverbAmount = 0.0f, delayAmount = 0.0f;\n            fxAmountsForSource (track.meta ? track.meta->routeIndex : 0, reverbAmount, delayAmount);\n            drawFxAura (dc, track, fieldArea, reverbAmount, delayAmount);\n            drawSpectralBody (dc, track, fieldArea);\n        }'''
new_draw = '''        std::sort (active.begin (), active.end (), [] (const DrawTrack& a, const DrawTrack& b)\n        {\n            if (!a.meta || !b.meta) return a.meta != nullptr;\n            return a.meta->mixerIndex < b.meta->mixerIndex;\n        });\n\n        const int depthCount = static_cast<int> (active.size ());\n        const float depthSpan = depthCount <= 1 ? 0.0f :\n            std::min (2.80f, 0.18f * static_cast<float> (depthCount - 1));\n        for (int i = 0; i < depthCount; ++i)\n        {\n            const float t = depthCount <= 1 ? 0.0f :\n                static_cast<float> (i) / static_cast<float> (depthCount - 1) - 0.5f;\n            active[static_cast<size_t> (i)].visualZ = t * depthSpan;\n        }\n\n        std::vector<DrawTrack> renderOrder = active;\n        std::sort (renderOrder.begin (), renderOrder.end (), [this] (const DrawTrack& a, const DrawTrack& b)\n        {\n            return cameraDepthForTrack (a) > cameraDepthForTrack (b);\n        });\n        for (const auto& track : renderOrder)\n        {\n            float reverbAmount = 0.0f, delayAmount = 0.0f;\n            fxAmountsForSource (track.meta ? track.meta->routeIndex : 0, reverbAmount, delayAmount);\n            drawFxAura (dc, track, fieldArea, reverbAmount, delayAmount);\n            drawSpectralBody (dc, track, fieldArea);\n        }'''
replace_once(old_draw, new_draw, "3D depth assignment/render order")

# V0.10 defaults to a small angle so the new depth is immediately visible, while double-click restores flat front view.
replace_once(
    "    HWND editorWindow = nullptr;\n",
    "    HWND editorWindow = nullptr;\n"
    "    bool orbitDragging = false;\n"
    "    POINT orbitLast {0, 0};\n"
    "    float orbitYaw = 0.34f;\n"
    "    float orbitPitch = -0.10f;\n"
    "    float orbitZoom = 1.0f;\n",
    "orbit members",
)

text = text.replace(
    "Persistent objects stay visible. FX returns use confidence + hysteresis, so false positives can recover without send-level flicker.",
    "3D view: drag to orbit, wheel to zoom. Z spacing is visual-only; audio reconstruction and FX logic remain unchanged."
)

out.write_text(text, encoding="utf-8")
print(out)
