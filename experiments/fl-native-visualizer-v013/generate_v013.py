from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v012_dir = root / "fl-native-visualizer-v012"

# Generate the validated V0.12 source first, including its stabilized V0.11/V0.12 wrappers.
runpy.run_path(str(v012_dir / "generate_v012_fixed.py"), run_name="__main__")
src = v012_dir / "generated" / "fieldv012.cpp"
out = here / "generated" / "fieldv013.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.13 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.13 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.13 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


# Fresh plugin identity.
text = text.replace("Field V0.12 Complete Room Tracking", "Field V0.13 Stable Depth + Axis Controls")
text = text.replace("FieldV012", "FieldV013")
text = text.replace("V0.12", "V0.13")
text = text.replace("V012", "V013")

# -----------------------------------------------------------------------------
# 1) Remove V0.12's hard-coded axis inversions. V0.13 uses explicit user controls.
# Telemetry stays in its raw measured orientation; projection decides whether to flip.
text = text.replace(
    "d.balance = -routeBalance[idx].load (std::memory_order_relaxed);",
    "d.balance = routeBalance[idx].load (std::memory_order_relaxed);"
)
replace_once(
    "        return 0.06f + (1.0f - t) * 0.96f;",
    "        const float displayT = invertY ? (1.0f - t) : t;\n"
    "        return 0.06f + displayT * 0.96f;",
    "Y inversion controlled by checkbox",
)
replace_once(
    "        const float X = wx;",
    "        const float X = invertX ? -wx : wx;",
    "X inversion controlled by checkbox",
)

# Add UI state beside the room camera state. Defaults are un-inverted because the V0.12
# hard flips were reported inverted in the latest FL Studio test.
replace_once(
    "    float orbitZoom = 1.0f;\n    std::array<float, kMaxRoutes> spatialDepth {};",
    "    float orbitZoom = 1.0f;\n"
    "    bool invertX = false;\n"
    "    bool invertY = false;\n"
    "    std::array<float, kMaxRoutes> spatialDepth {};\n"
    "    std::array<unsigned char, kMaxRoutes> spatialDepthClass {};\n"
    "    std::array<unsigned char, kMaxRoutes> spatialDepthCandidate {};\n"
    "    std::array<int, kMaxRoutes> spatialDepthCandidateFrames {};",
    "axis + stable-depth state",
)

# Checkbox renderer.
checkbox_helper = r'''    static void drawCheckbox (HDC dc, const RECT& rect, const wchar_t* text, bool checked)
    {
        const int boxSize = 15;
        const int top = rect.top + (rect.bottom - rect.top - boxSize) / 2;
        RECT box {rect.left, top, rect.left + boxSize, top + boxSize};
        HBRUSH fill = CreateSolidBrush (checked ? RGB (42, 126, 116) : RGB (24, 31, 40));
        FillRect (dc, &box, fill);
        DeleteObject (fill);
        HPEN pen = CreatePen (PS_SOLID, 1, checked ? RGB (91, 210, 195) : RGB (82, 96, 112));
        auto oldPen = SelectObject (dc, pen);
        auto oldBrush = SelectObject (dc, GetStockObject (NULL_BRUSH));
        Rectangle (dc, box.left, box.top, box.right, box.bottom);
        if (checked)
        {
            MoveToEx (dc, box.left + 3, box.top + 8, nullptr);
            LineTo (dc, box.left + 6, box.bottom - 3);
            LineTo (dc, box.right - 2, box.top + 3);
        }
        SelectObject (dc, oldBrush);
        SelectObject (dc, oldPen);
        DeleteObject (pen);
        SetTextColor (dc, checked ? RGB (220, 240, 236) : RGB (174, 190, 207));
        RECT label {box.right + 6, rect.top, rect.right, rect.bottom};
        DrawTextW (dc, text, -1, &label, DT_LEFT | DT_SINGLELINE | DT_VCENTER);
    }

'''
replace_once(
    "    static int yForFrequency (float hz, int top, int bottom)",
    checkbox_helper + "    static int yForFrequency (float hz, int top, int bottom)",
    "checkbox renderer",
)

# Top-bar checkbox hit targets. They live above the orbit area so drag capture cannot swallow them.
replace_once(
    "        else if (x >= 340 && x < 485)\n            mode.store (static_cast<int> (EngineMode::Null), std::memory_order_relaxed);",
    "        else if (x >= 340 && x < 485)\n"
    "            mode.store (static_cast<int> (EngineMode::Null), std::memory_order_relaxed);\n"
    "        else if (x >= 500 && x < 590)\n"
    "            invertX = !invertX;\n"
    "        else if (x >= 600 && x < 690)\n"
    "            invertY = !invertY;",
    "axis checkbox click handling",
)

replace_once(
    "        drawButton (dc, RECT {340, 68, 485, 104}, L\"NULL CHECK\", currentMode == EngineMode::Null);",
    "        drawButton (dc, RECT {340, 68, 485, 104}, L\"NULL CHECK\", currentMode == EngineMode::Null);\n"
    "        drawCheckbox (dc, RECT {500, 72, 590, 100}, L\"Invert X\", invertX);\n"
    "        drawCheckbox (dc, RECT {600, 72, 690, 100}, L\"Invert Y\", invertY);",
    "draw axis checkboxes",
)
text = text.replace(
    "        r = {505, 70, client.right - 20, 103};",
    "        r = {705, 70, client.right - 20, 103};"
)

# -----------------------------------------------------------------------------
# 2) AUX names are commonly FL send/return channels. Treat AUX as a return hint, but still
# require actual source-associated temporal evidence before hiding it as a primary object.
replace_once(
    '        if (has ("return") || has ("send") || has ("wet") || has ("fx"))',
    '        if (has ("return") || has ("send") || has ("wet") || has ("fx") || has ("aux"))',
    "AUX return name hint",
)
text = text.replace(
    "        const float confidenceNeeded = hinted ? 0.69f : 0.90f;\n"
    "        const float linkNeeded = hinted ? 0.30f : 0.58f;",
    "        const float confidenceNeeded = hinted ? 0.58f : 0.88f;\n"
    "        const float linkNeeded = hinted ? 0.28f : 0.56f;"
)

# High-confidence FX returns stay in telemetry internally, but do not appear as separate PRIMARY
# TRACKS in the sidebar. This preserves full route learning without presenting reverb AUXes as
# instruments. The primary-body gate uses the same source-associated evidence.
sidebar_start = text.find("        std::vector<DrawTrack> stableList;")
if sidebar_start < 0:
    raise RuntimeError("V0.13 could not find sidebar list")
sidebar_end = text.find("        std::sort (stableList.begin ()", sidebar_start)
if sidebar_end < 0:
    raise RuntimeError("V0.13 could not find sidebar sort")
sidebar_block = text[sidebar_start:sidebar_end]
needle = (
    "            if (!everActive[idx].load (std::memory_order_relaxed))\n"
    "                continue;\n"
)
if needle not in sidebar_block:
    raise RuntimeError("V0.13 could not find sidebar ever-active gate")
sidebar_block = sidebar_block.replace(
    needle,
    needle +
    "            if (shouldHideAsFxVisualReturn (item.routeIndex))\n"
    "                continue;\n",
    1,
)
text = text[:sidebar_start] + sidebar_block + text[sidebar_end:]
text = text.replace('DrawTextW (dc, L"ACTIVE TRACKS"', 'DrawTextW (dc, L"PRIMARY TRACKS"', 1)

# Show attached temporal FX on the source row rather than as a separate AUX row.
sidebar_start = text.find("        std::vector<DrawTrack> stableList;")
sidebar_end = text.find("        if (currentMode == EngineMode::Bypass)", sidebar_start)
sidebar_block = text[sidebar_start:sidebar_end]
name_needle = (
    "            if (display.empty ())\n"
    "                display = \"(unnamed)\";\n"
)
if name_needle in sidebar_block:
    sidebar_block = sidebar_block.replace(
        name_needle,
        name_needle +
        "            float rowReverb = 0.0f, rowDelay = 0.0f;\n"
        "            fxAmountsForSource (item.routeIndex, rowReverb, rowDelay);\n"
        "            if (rowReverb > 0.010f) display += \"  +REV\";\n"
        "            if (rowDelay > 0.010f) display += \"  +DLY\";\n",
        1,
    )
    text = text[:sidebar_start] + sidebar_block + text[sidebar_end:]

# -----------------------------------------------------------------------------
# 3) Stable Z. V0.11/0.12 used peak level and width in the target depth, which causes large
# front/back motion even without automation because normal musical dynamics change every block.
# V0.13 removes level and width entirely from Z. Depth is a latched topology class:
# dry / delay-associated / reverb-associated / both. A new class must persist for ~45 paint
# frames before it is committed, after which the one transition is smoothed and then stops.
stable_depth = r'''        // Stable apparent depth: musical level and width NEVER drive Z.
        // Only a persistent change in attached temporal-FX topology can change the depth class.
        for (auto& track : active)
        {
            if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
                continue;

            const size_t idx = static_cast<size_t> (track.meta->routeIndex - 1);
            float reverbAmount = 0.0f, delayAmount = 0.0f;
            fxAmountsForSource (track.meta->routeIndex, reverbAmount, delayAmount);
            const unsigned char observedClass = static_cast<unsigned char> (
                (reverbAmount > 0.015f ? 1 : 0) | (delayAmount > 0.015f ? 2 : 0));

            float& smoothDepth = spatialDepth[idx];
            if (smoothDepth <= 0.001f)
            {
                spatialDepthClass[idx] = observedClass;
                spatialDepthCandidate[idx] = observedClass;
                spatialDepthCandidateFrames[idx] = 0;
            }
            else if (observedClass != spatialDepthClass[idx])
            {
                if (spatialDepthCandidate[idx] == observedClass)
                    ++spatialDepthCandidateFrames[idx];
                else
                {
                    spatialDepthCandidate[idx] = observedClass;
                    spatialDepthCandidateFrames[idx] = 1;
                }
                if (spatialDepthCandidateFrames[idx] >= 45)
                {
                    spatialDepthClass[idx] = observedClass;
                    spatialDepthCandidateFrames[idx] = 0;
                }
            }
            else
            {
                spatialDepthCandidate[idx] = observedClass;
                spatialDepthCandidateFrames[idx] = 0;
            }

            float targetDepth = 0.20f; // dry source
            switch (spatialDepthClass[idx])
            {
                case 1: targetDepth = 0.58f; break; // reverb-associated
                case 2: targetDepth = 0.42f; break; // delay-associated
                case 3: targetDepth = 0.66f; break; // both
                default: break;
            }

            if (smoothDepth <= 0.001f)
                smoothDepth = targetDepth;
            else
            {
                const float delta = targetDepth - smoothDepth;
                if (std::abs (delta) <= 0.0015f)
                    smoothDepth = targetDepth;
                else
                    smoothDepth += delta * 0.035f;
            }

            track.visualZ = smoothDepth;
            track.volumeThickness = 0.070f;
        }

'''
replace_between(
    "        // Actual room placement from the signal we can observe: X is measured stereo balance.\n",
    "        std::vector<DrawTrack> renderOrder = active;",
    stable_depth,
    "stable Z topology model",
)

# UI language reflects the new controls and stable Z model.
text = text.replace(
    "3D view: drag to orbit, wheel to zoom. Z spacing is visual-only; audio reconstruction and FX logic remain unchanged.",
    "Stable Z ignores gain dynamics. Use Invert X / Invert Y if the DAW orientation reads backwards."
)
text = text.replace(
    "X PAN   |   Y FREQUENCY   |   Z APPARENT DEPTH     DRAG ORBIT / WHEEL ZOOM / DOUBLE-CLICK RESET",
    "X PAN   |   Y FREQUENCY   |   Z LATCHED DEPTH     DRAG ORBIT / WHEEL ZOOM / DOUBLE-CLICK RESET"
)

out.write_text(text, encoding="utf-8")
print(out)
