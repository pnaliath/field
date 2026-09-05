from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v023 = root / "fl-native-visualizer-v023"

# Start from compile-green V0.23 including diagnostic columns.
runpy.run_path(str(v023 / "generate_v023_fixed.py"), run_name="__main__")
src = v023 / "generated" / "fieldv023.cpp"
out = here / "generated" / "fieldv024.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.24 could not find patch point: {label}")
    text = text.replace(old, new, 1)


# Fresh identity.
text = text.replace("Field V0.23", "Field V0.24")
text = text.replace("FieldV023", "FieldV024")
text = text.replace("V023", "V024")
text = text.replace("v023", "v024")
text = text.replace("FieldV023_diagnostics.csv", "FieldV024_diagnostics.csv")
text = text.replace("WEB GEOMETRY + LIVE PAN", "AXIS SENSITIVITY CALIBRATION")

# -----------------------------------------------------------------------------
# Calibration state. These are deliberately render-mapping controls only:
# analysis, clustering and temporal response coefficients remain unchanged.
replace_once(
    "    float orbitZoom = 1.0f;\n",
    "    float orbitZoom = 1.0f;\n"
    "    float xAxisSensitivity = 1.0f;\n"
    "    float zAxisSensitivity = 1.0f;\n",
    "axis sensitivity state",
)

# X sensitivity multiplies the rendered pan coordinate around centre. It does not
# alter the analyser or the L/R voice classifier, so calibration is interpretable.
replace_once(
    "                d.balance = livePan;",
    "                d.balance = std::clamp (livePan * xAxisSensitivity, -1.0f, 1.0f);",
    "single-body X sensitivity",
)
replace_once(
    "                d.balance = std::clamp (learnedCentre + shift, -1.0f, 1.0f);",
    "                d.balance = std::clamp ((learnedCentre + shift) * xAxisSensitivity, -1.0f, 1.0f);",
    "split-body X sensitivity",
)

# Z sensitivity expands/compresses the existing absolute depth mapping around the
# room midpoint. 1.00x is V0.23 behavior; >1 spreads tracks more front/back.
replace_once(
    "            const float targetDepth = 0.10f + backness * 0.72f;",
    "            const float baseDepth = 0.10f + backness * 0.72f;\n"
    "            const float targetDepth = std::clamp (\n"
    "                0.46f + (baseDepth - 0.46f) * zAxisSensitivity, 0.08f, 0.84f);",
    "Z sensitivity around room midpoint",
)

# -----------------------------------------------------------------------------
# Small GDI rotary control. Left-half click decrements, right-half increments;
# Ctrl+click resets to 1.00x. Numeric value is always visible for test reporting.
knob_helper = r'''    static void drawSensitivityKnob (HDC dc, const RECT& rect, const wchar_t* label, float value)
    {
        const int cx = (rect.left + rect.right) / 2;
        const int cy = rect.top + 19;
        const int radius = 15;
        HBRUSH fill = CreateSolidBrush (RGB (24, 31, 40));
        HPEN rim = CreatePen (PS_SOLID, 1, RGB (75, 91, 108));
        auto oldBrush = SelectObject (dc, fill);
        auto oldPen = SelectObject (dc, rim);
        Ellipse (dc, cx - radius, cy - radius, cx + radius + 1, cy + radius + 1);

        const float norm = std::clamp ((value - 0.25f) / 2.75f, 0.0f, 1.0f);
        const float angle = (-2.35619449f) + norm * 4.71238898f;
        const int px = cx + static_cast<int> (std::cos (angle) * 10.0f);
        const int py = cy + static_cast<int> (std::sin (angle) * 10.0f);
        HPEN pointerPen = CreatePen (PS_SOLID, 2, RGB (96, 214, 198));
        SelectObject (dc, pointerPen);
        MoveToEx (dc, cx, cy, nullptr);
        LineTo (dc, px, py);
        SelectObject (dc, oldPen);
        DeleteObject (pointerPen);
        SelectObject (dc, oldBrush);
        DeleteObject (rim);
        DeleteObject (fill);

        SetBkMode (dc, TRANSPARENT);
        SetTextColor (dc, RGB (181, 197, 214));
        RECT labelRect {rect.left, rect.top + 35, rect.right, rect.top + 49};
        DrawTextW (dc, label, -1, &labelRect, DT_CENTER | DT_SINGLELINE | DT_VCENTER);
        wchar_t valueText[24] {};
        swprintf_s (valueText, L"%.2fx", value);
        SetTextColor (dc, RGB (96, 214, 198));
        RECT valueRect {rect.left, rect.top + 48, rect.right, rect.bottom};
        DrawTextW (dc, valueText, -1, &valueRect, DT_CENTER | DT_SINGLELINE | DT_VCENTER);

        SetTextColor (dc, RGB (93, 108, 124));
        RECT minusRect {rect.left, rect.top + 9, cx - radius - 2, rect.top + 29};
        RECT plusRect {cx + radius + 2, rect.top + 9, rect.right, rect.top + 29};
        DrawTextW (dc, L"-", -1, &minusRect, DT_CENTER | DT_SINGLELINE | DT_VCENTER);
        DrawTextW (dc, L"+", -1, &plusRect, DT_CENTER | DT_SINGLELINE | DT_VCENTER);
    }

    static void adjustSensitivity (float& value, int x, int centreX)
    {
        if ((GetKeyState (VK_CONTROL) & 0x8000) != 0)
        {
            value = 1.0f;
            return;
        }
        const float step = ((GetKeyState (VK_SHIFT) & 0x8000) != 0) ? 0.25f : 0.10f;
        value += x < centreX ? -step : step;
        value = std::clamp (std::round (value * 100.0f) / 100.0f, 0.25f, 3.0f);
    }

'''
replace_once(
    "    static int yForFrequency (float hz, int top, int bottom)",
    knob_helper + "    static int yForFrequency (float hz, int top, int bottom)",
    "sensitivity knob helpers",
)

# Reuse the top control strip after the drag inversion checkboxes.
replace_once(
    "        else if (x >= 600 && x < 690)\n            invertY = !invertY;",
    "        else if (x >= 600 && x < 690)\n"
    "            invertY = !invertY;\n"
    "        else if (x >= 700 && x < 780 && y >= 60 && y < 122)\n"
    "            adjustSensitivity (xAxisSensitivity, x, 740);\n"
    "        else if (x >= 785 && x < 865 && y >= 60 && y < 122)\n"
    "            adjustSensitivity (zAxisSensitivity, x, 825);",
    "sensitivity knob click handling",
)

replace_once(
    "        drawCheckbox (dc, RECT {600, 72, 690, 100}, L\"Invert drag Y\", invertY);",
    "        drawCheckbox (dc, RECT {600, 72, 690, 100}, L\"Invert drag Y\", invertY);\n"
    "        drawSensitivityKnob (dc, RECT {700, 61, 780, 122}, L\"X SENS\", xAxisSensitivity);\n"
    "        drawSensitivityKnob (dc, RECT {785, 61, 865, 122}, L\"Z SENS\", zAxisSensitivity);",
    "draw sensitivity knobs",
)

# Give the knobs their own top-strip space; move descriptive copy to the right.
text = text.replace(
    "        r = {705, 70, client.right - 20, 103};",
    "        r = {880, 70, client.right - 20, 103};",
    1,
)

# -----------------------------------------------------------------------------
# Diagnostics carry the exact calibration values on every row.
old_header = "tick_ms,route,name,block_ms,render_ms,render_pct,paint_ms,peak_db,fast_rms_db,presence,learned_loud_db,z,profile_ready,dominant_hz,low_hz,high_hz,onset_count,onset_to_presence_ms,onset_to_profile_ms,onset_to_draw_ms,voice_count,voice_pan_0,voice_pan_1,voice_pan_2,live_pan,live_width,depth_level_db,pan_shift\\n"
new_header = "tick_ms,route,name,block_ms,render_ms,render_pct,paint_ms,peak_db,fast_rms_db,presence,learned_loud_db,z,profile_ready,dominant_hz,low_hz,high_hz,onset_count,onset_to_presence_ms,onset_to_profile_ms,onset_to_draw_ms,voice_count,voice_pan_0,voice_pan_1,voice_pan_2,live_pan,live_width,depth_level_db,pan_shift,x_sens,z_sens\\n"
replace_once(old_header, new_header, "diagnostics sensitivity header")

old_fmt = "%llu,%d,%s,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.4f,%.2f,%.4f,%d,%.1f,%.1f,%.1f,%u,%.1f,%.1f,%.1f,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%.4f\\n"
new_fmt = "%llu,%d,%s,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.4f,%.2f,%.4f,%d,%.1f,%.1f,%.1f,%u,%.1f,%.1f,%.1f,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%.4f,%.2f,%.2f\\n"
replace_once(old_fmt, new_fmt, "diagnostics sensitivity format")

old_tail = "                routeLiveWidth[idx].load (std::memory_order_relaxed),\n                routeDepthLevelDb[idx].load (std::memory_order_relaxed),\n                routeSpatialPanShift[idx].load (std::memory_order_relaxed));"
new_tail = "                routeLiveWidth[idx].load (std::memory_order_relaxed),\n                routeDepthLevelDb[idx].load (std::memory_order_relaxed),\n                routeSpatialPanShift[idx].load (std::memory_order_relaxed),\n                xAxisSensitivity,\n                zAxisSensitivity);"
replace_once(old_tail, new_tail, "diagnostics sensitivity tail")

text = text.replace(
    "V0.23 live pan + continuous width + active-RMS depth + web lobe renderer",
    "V0.24 calibration: X SENS and Z SENS are test-only render mapping controls"
)

out.write_text(text, encoding="utf-8")
print(out)
