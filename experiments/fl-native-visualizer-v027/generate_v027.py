from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v026 = root / "fl-native-visualizer-v026"

# Start from compile-green V0.26 frozen-hit-tail build.
runpy.run_path(str(v026 / "generate_v026.py"), run_name="__main__")
src = v026 / "generated" / "fieldv026.cpp"
out = here / "generated" / "fieldv027.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.27 could not find patch point: {label}")
    text = text.replace(old, new, 1)


# Identity.
text = text.replace("Field V0.26", "Field V0.27")
text = text.replace("FieldV026", "FieldV027")
text = text.replace("V026", "V027")
text = text.replace("v026", "v027")
text = text.replace("FieldV026_diagnostics.csv", "FieldV027_diagnostics.csv")
text = text.replace("FROZEN HIT TAILS", "STABLE WIDTH + DISAPPEAR TEST")

# -----------------------------------------------------------------------------
# 1) Geometry width must be identity, not momentary envelope telemetry.
# V0.26 fed routeLiveWidth directly into every event copy. routeLiveWidth intentionally
# converges from the current block, so the first frame of a hit could be visibly narrower.
# routeWidth is the long-term energy-weighted stereo identity learned since V0.15.
replace_once(
    "            const float liveWidth = routeLiveWidth[idx].load (std::memory_order_relaxed);",
    "            const float liveWidth = routeLiveWidth[idx].load (std::memory_order_relaxed);\n"
    "            const float learnedWidth = clamp01 (routeWidth[idx].load (std::memory_order_relaxed));\n"
    "            const float stableWidth = routeProfileReady[idx].load (std::memory_order_relaxed)\n"
    "                ? learnedWidth : liveWidth;",
    "stable learned stereo width",
)

width_uses = text.count("d.width = liveWidth;")
if width_uses < 2:
    raise RuntimeError(f"V0.27 expected multiple live-width render uses, found {width_uses}")
text = text.replace("d.width = liveWidth;", "d.width = stableWidth;")

# -----------------------------------------------------------------------------
# 2) Test-only disappear-time control. This is total transient snapshot lifetime,
# measured from onset to opacity zero. Sustained material still falls back to its live body.
replace_once(
    "    float zAxisSensitivity = 1.20f;\n",
    "    float zAxisSensitivity = 1.20f;\n"
    "    float disappearTimeMs = 440.0f;\n",
    "disappear-time state",
)

slider_helpers = r'''    static void drawDisappearSlider (HDC dc, const RECT& rect, float valueMs)
    {
        constexpr float minMs = 120.0f;
        constexpr float maxMs = 1400.0f;
        const int left = rect.left + 8;
        const int right = rect.right - 8;
        const int trackY = rect.top + 25;
        const float norm = clamp01 ((valueMs - minMs) / (maxMs - minMs));
        const int thumbX = left + static_cast<int> (norm * static_cast<float> (right - left));

        SetBkMode (dc, TRANSPARENT);
        SetTextColor (dc, RGB (181, 197, 214));
        RECT labelRect {rect.left, rect.top, rect.right, rect.top + 16};
        DrawTextW (dc, L"DISAPPEAR", -1, &labelRect, DT_CENTER | DT_SINGLELINE | DT_VCENTER);

        HPEN basePen = CreatePen (PS_SOLID, 2, RGB (64, 79, 95));
        auto oldPen = SelectObject (dc, basePen);
        MoveToEx (dc, left, trackY, nullptr);
        LineTo (dc, right, trackY);

        HPEN activePen = CreatePen (PS_SOLID, 3, RGB (96, 214, 198));
        SelectObject (dc, activePen);
        MoveToEx (dc, left, trackY, nullptr);
        LineTo (dc, thumbX, trackY);

        HBRUSH thumbBrush = CreateSolidBrush (RGB (96, 214, 198));
        auto oldBrush = SelectObject (dc, thumbBrush);
        Ellipse (dc, thumbX - 5, trackY - 5, thumbX + 6, trackY + 6);
        SelectObject (dc, oldBrush);
        SelectObject (dc, oldPen);
        DeleteObject (thumbBrush);
        DeleteObject (activePen);
        DeleteObject (basePen);

        wchar_t valueText[32] {};
        swprintf_s (valueText, L"%.0f ms", valueMs);
        SetTextColor (dc, RGB (96, 214, 198));
        RECT valueRect {rect.left, rect.top + 34, rect.right, rect.bottom};
        DrawTextW (dc, valueText, -1, &valueRect, DT_CENTER | DT_SINGLELINE | DT_VCENTER);
    }

    static void setDisappearSlider (float& valueMs, int x, const RECT& rect)
    {
        constexpr float minMs = 120.0f;
        constexpr float maxMs = 1400.0f;
        const int left = rect.left + 8;
        const int right = rect.right - 8;
        const float t = clamp01 (static_cast<float> (x - left) /
            static_cast<float> (std::max (1, right - left)));
        const float raw = minMs + t * (maxMs - minMs);
        valueMs = std::clamp (std::round (raw / 10.0f) * 10.0f, minMs, maxMs);
    }

'''
replace_once(
    "    static int yForFrequency (float hz, int top, int bottom)",
    slider_helpers + "    static int yForFrequency (float hz, int top, int bottom)",
    "disappear slider helpers",
)

replace_once(
    "        else if (x >= 785 && x < 865 && y >= 60 && y < 122)\n"
    "            adjustSensitivity (zAxisSensitivity, x, 825);",
    "        else if (x >= 785 && x < 865 && y >= 60 && y < 122)\n"
    "            adjustSensitivity (zAxisSensitivity, x, 825);\n"
    "        else if (x >= 880 && x < 1110 && y >= 60 && y < 122)\n"
    "            setDisappearSlider (disappearTimeMs, x, RECT {880, 62, 1110, 120});",
    "disappear slider click handling",
)

replace_once(
    "        drawSensitivityKnob (dc, RECT {785, 61, 865, 122}, L\"Z SENS\", zAxisSensitivity);",
    "        drawSensitivityKnob (dc, RECT {785, 61, 865, 122}, L\"Z SENS\", zAxisSensitivity);\n"
    "        drawDisappearSlider (dc, RECT {880, 62, 1110, 120}, disappearTimeMs);",
    "draw disappear slider",
)

# Move descriptive copy out of the new slider's area.
text = text.replace(
    "        r = {880, 70, client.right - 20, 103};",
    "        r = {1125, 70, client.right - 20, 103};",
    1,
)

# -----------------------------------------------------------------------------
# 3) Make the slider the single source of truth for transient snapshot lifetime.
# A short hold preserves punch; the remaining time is a linear fade. No hidden
# route-presence tail may keep an ended hit visible after the selected lifetime.
replace_once(
    "            int recentCount = 0;\n",
    "            int recentCount = 0;\n"
    "            const float snapshotLifeMs = std::clamp (disappearTimeMs, 120.0f, 1400.0f);\n"
    "            const float snapshotHoldMs = std::min (90.0f, snapshotLifeMs * 0.22f);\n"
    "            const float snapshotFadeMs = std::max (1.0f, snapshotLifeMs - snapshotHoldMs);\n",
    "snapshot lifetime parameters",
)

replace_once(
    "                if (born == 0ull || visualNow < born || visualNow - born >= 440ull)\n",
    "                if (born == 0ull || visualNow < born ||\n"
    "                    static_cast<float> (visualNow - born) >= snapshotLifeMs)\n",
    "dynamic snapshot lifetime gate",
)

replace_once(
    "                    const float eventFade = ageMs <= 90.0f ? 1.0f :\n"
    "                        clamp01 (1.0f - (ageMs - 90.0f) / 350.0f);\n"
    "                    const float routeTailPresence = clamp01 (routeVisualPresence[idx].load (\n"
    "                        std::memory_order_relaxed));\n"
    "                    const float fade = ev.slot == newestSlot\n"
    "                        ? std::max (eventFade, routeTailPresence)\n"
    "                        : eventFade;",
    "                    const float fade = ageMs <= snapshotHoldMs ? 1.0f :\n"
    "                        clamp01 (1.0f - (ageMs - snapshotHoldMs) / snapshotFadeMs);",
    "slider-controlled event fade",
)

# V0.26 reconstructed the latest event after the fixed 440 ms window using the
# independent routeVisualPresence release. That defeats a disappear-time calibration.
# Use the same selected lifetime here, so an ended hit cannot resurrect or outlive it.
replace_once(
    "                const float tailPresence = clamp01 (routeVisualPresence[idx].load (\n"
    "                    std::memory_order_relaxed));\n"
    "                if (latestBorn != 0ull && tailPresence > 0.010f)",
    "                const float latestAgeMs = (latestBorn != 0ull && visualNow >= latestBorn)\n"
    "                    ? static_cast<float> (visualNow - latestBorn) : snapshotLifeMs + 1.0f;\n"
    "                const float tailPresence = latestAgeMs <= snapshotHoldMs ? 1.0f :\n"
    "                    clamp01 (1.0f - (latestAgeMs - snapshotHoldMs) / snapshotFadeMs);\n"
    "                if (latestBorn != 0ull && latestAgeMs < snapshotLifeMs && tailPresence > 0.010f)",
    "slider-controlled frozen tail",
)

# Diagnostics include the exact calibration value selected in the UI when the
# inherited V0.24 columns are present.
old_header = "tick_ms,route,name,block_ms,render_ms,render_pct,paint_ms,peak_db,fast_rms_db,presence,learned_loud_db,z,profile_ready,dominant_hz,low_hz,high_hz,onset_count,onset_to_presence_ms,onset_to_profile_ms,onset_to_draw_ms,voice_count,voice_pan_0,voice_pan_1,voice_pan_2,live_pan,live_width,depth_level_db,pan_shift,x_sens,z_sens\\n"
new_header = "tick_ms,route,name,block_ms,render_ms,render_pct,paint_ms,peak_db,fast_rms_db,presence,learned_loud_db,z,profile_ready,dominant_hz,low_hz,high_hz,onset_count,onset_to_presence_ms,onset_to_profile_ms,onset_to_draw_ms,voice_count,voice_pan_0,voice_pan_1,voice_pan_2,live_pan,live_width,depth_level_db,pan_shift,x_sens,z_sens,disappear_ms\\n"
if old_header in text:
    text = text.replace(old_header, new_header, 1)
    old_fmt = "%llu,%d,%s,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.4f,%.2f,%.4f,%d,%.1f,%.1f,%.1f,%u,%.1f,%.1f,%.1f,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%.4f,%.2f,%.2f\\n"
    new_fmt = "%llu,%d,%s,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.4f,%.2f,%.4f,%d,%.1f,%.1f,%.1f,%u,%.1f,%.1f,%.1f,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%.4f,%.2f,%.2f,%.0f\\n"
    if old_fmt not in text:
        raise RuntimeError("V0.27 diagnostics format marker missing")
    text = text.replace(old_fmt, new_fmt, 1)
    old_tail = "                xAxisSensitivity,\n                zAxisSensitivity);"
    new_tail = "                xAxisSensitivity,\n                zAxisSensitivity,\n                disappearTimeMs);"
    if old_tail not in text:
        raise RuntimeError("V0.27 diagnostics tail marker missing")
    text = text.replace(old_tail, new_tail, 1)

text = text.replace(
    "V0.26 frozen hit tails: X/Z remain immutable until opacity reaches zero",
    "V0.27 stable learned width + testable transient disappear lifetime"
)

out.write_text(text, encoding="utf-8")
print(out)
