from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v015 = root / "fl-native-visualizer-v015"

runpy.run_path(str(v015 / "generate_v015_fixed.py"), run_name="__main__")
src = v015 / "generated" / "fieldv015.cpp"
out = here / "generated" / "fieldv016.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.16 could not find patch point: {label}")
    text = text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# Fresh identity.
text = text.replace("Field V0.15", "Field V0.16")
text = text.replace("FieldV015", "FieldV016")
text = text.replace("V015", "V016")
text = text.replace("v015", "v016")

# -----------------------------------------------------------------------------
# Presence is visual activity only. Learned geometry is retained, but a paused/
# silent track must actually disappear like the web prototype rather than leave
# a fully readable frozen sculpture. Gamma < 1 keeps genuinely quiet material visible.
presence_helper = r'''
    float visualPresenceForTrack (const DrawTrack& track) const
    {
        const float linearPresence = clamp01 ((track.peakDb + 114.0f) / 78.0f);
        if (linearPresence <= 0.0f)
            return 0.0f;
        return std::pow (linearPresence, 0.65f);
    }

'''
replace_once(
    "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)\n    {",
    presence_helper + "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)\n    {",
    "visual presence helper",
)

# FX haze/echo must follow the source activity too; otherwise a paused session can
# still display floating return auras after the body disappears.
replace_once(
    "        if (!track.meta || (reverbAmount <= 0.01f && delayAmount <= 0.01f))\n            return;",
    "        if (!track.meta || (reverbAmount <= 0.01f && delayAmount <= 0.01f))\n"
    "            return;\n"
    "        const float sourcePresence = visualPresenceForTrack (track);\n"
    "        if (sourcePresence <= 0.012f)\n"
    "            return;\n"
    "        reverbAmount *= sourcePresence;\n"
    "        delayAmount *= sourcePresence;",
    "FX aura follows source presence",
)

# Spectral body: fully absent at silence. During decay the existing smoothed peak
# naturally provides the fade. Quiet active tracks remain legible via the 0.65 gamma.
replace_once(
    "        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))\n            return;\n\n        const float halfDepth",
    "        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))\n"
    "            return;\n"
    "        const float presence = visualPresenceForTrack (track);\n"
    "        if (presence <= 0.012f)\n"
    "            return;\n\n"
    "        const float halfDepth",
    "silent learned body disappears",
)
replace_once(
    "        const float presence = clamp01 ((track.peakDb + 114.0f) / 78.0f);\n"
    "        const COLORREF frontFill = mixColor (raw, bg, 0.82f - presence * 0.26f);\n"
    "        const COLORREF backFill = mixColor (raw, bg, 0.91f - presence * 0.13f);\n"
    "        const COLORREF sideFill = mixColor (raw, bg, 0.88f - presence * 0.18f);\n"
    "        const COLORREF brightOutline = mixColor (raw, RGB (242, 248, 255), 0.18f);\n"
    "        const COLORREF outline = mixColor (brightOutline, bg, (1.0f - presence) * 0.66f);",
    "        const COLORREF frontFill = mixColor (raw, bg, 0.985f - presence * 0.425f);\n"
    "        const COLORREF backFill = mixColor (raw, bg, 0.995f - presence * 0.255f);\n"
    "        const COLORREF sideFill = mixColor (raw, bg, 0.992f - presence * 0.325f);\n"
    "        const COLORREF brightOutline = mixColor (raw, RGB (242, 248, 255), 0.18f);\n"
    "        const COLORREF outline = mixColor (brightOutline, bg, 0.97f - presence * 0.80f);",
    "presence-scaled body colours",
)

# Identity trace should not survive after the sound has faded out.
replace_once(
    "        const float halfDepth = std::clamp (track.volumeThickness * 0.5f, 0.018f, 0.10f);\n"
    "        const float zFront = std::clamp (track.visualZ - halfDepth, 0.01f, 0.98f);\n"
    "        const auto front = projectedBodyPointsAtDepth (track, area, zFront);\n"
    "        COLORREF raw = fieldRouteColor (*track.meta);\n"
    "        const float presence = clamp01 ((track.peakDb + 114.0f) / 78.0f);",
    "        const float presence = visualPresenceForTrack (track);\n"
    "        if (presence <= 0.012f)\n"
    "            return;\n"
    "        const float halfDepth = std::clamp (track.volumeThickness * 0.5f, 0.018f, 0.10f);\n"
    "        const float zFront = std::clamp (track.visualZ - halfDepth, 0.01f, 0.98f);\n"
    "        const auto front = projectedBodyPointsAtDepth (track, area, zFront);\n"
    "        COLORREF raw = fieldRouteColor (*track.meta);",
    "identity trace follows presence",
)
replace_once(
    "        const COLORREF line = mixColor (lineBase, RGB (16, 20, 26), (1.0f - presence) * 0.72f);",
    "        const COLORREF line = mixColor (lineBase, RGB (16, 20, 26), 0.94f - presence * 0.76f);",
    "identity trace fade curve",
)

# -----------------------------------------------------------------------------
# Vertical track labels drawn directly on the front surface of each audible body.
# They are an overlay only and do not affect hit testing or geometry.
label_function = r'''
    void drawTrackNameOnBody (HDC dc, const DrawTrack& track, const RECT& area)
    {
        if (!track.meta)
            return;
        const int route = track.meta->routeIndex;
        if (route < 1 || route > kMaxRoutes)
            return;
        const size_t idx = static_cast<size_t> (route - 1);
        if (!routeProfileReady[idx].load (std::memory_order_relaxed))
            return;
        const float presence = visualPresenceForTrack (track);
        if (presence <= 0.045f)
            return;

        std::string display = !track.meta->visibleName.empty () ? track.meta->visibleName : track.meta->userName;
        if (display.empty ())
            display = "Track " + std::to_string (track.meta->mixerIndex >= 0 ? track.meta->mixerIndex : route);
        constexpr size_t kMaxLabelChars = 20;
        if (display.size () > kMaxLabelChars)
            display = display.substr (0, kMaxLabelChars - 1) + "...";
        const auto wide = ansiToWide (display);
        if (wide.empty ())
            return;

        const float halfDepth = std::clamp (track.volumeThickness * 0.5f, 0.018f, 0.10f);
        const float zFront = std::clamp (track.visualZ - halfDepth - 0.002f, 0.008f, 0.98f);
        const auto anchor = projectWorld (track.balance, 0.50f, zFront, area);

        HFONT verticalFont = CreateFontW (-13, 0, 900, 900, FW_SEMIBOLD, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        auto oldFont = SelectObject (dc, verticalFont);
        const UINT oldAlign = SetTextAlign (dc, TA_CENTER | TA_BASELINE);
        COLORREF raw = fieldRouteColor (*track.meta);
        const COLORREF labelBase = mixColor (raw, RGB (248, 251, 255), 0.58f);
        SetTextColor (dc, mixColor (labelBase, RGB (16, 20, 26), 0.20f - 0.14f * presence));
        SetBkMode (dc, TRANSPARENT);
        TextOutW (dc, anchor.x + 2, anchor.y, wide.c_str (), static_cast<int> (wide.size ()));
        SetTextAlign (dc, oldAlign);
        SelectObject (dc, oldFont);
        DeleteObject (verticalFont);
    }

'''
replace_once(
    "    void paint (HWND hwnd)\n    {",
    label_function + "    void paint (HWND hwnd)\n    {",
    "vertical track labels",
)
replace_once(
    "        // Readability overlay only; object positions remain their inferred room coordinates.\n"
    "        for (const auto& track : renderOrder)\n"
    "            drawIdentityTrace (dc, track, fieldArea);",
    "        // Readability overlays only; object positions remain their inferred room coordinates.\n"
    "        for (const auto& track : renderOrder)\n"
    "            drawIdentityTrace (dc, track, fieldArea);\n"
    "        for (const auto& track : renderOrder)\n"
    "            drawTrackNameOnBody (dc, track, fieldArea);",
    "draw vertical labels after bodies",
)

# -----------------------------------------------------------------------------
# Sidebar membership is routing-based and stable. It no longer depends on current
# signal, learned state, or FX-return classifier confidence. Learning affects the
# body, never which rows exist in the list.
text = text.replace('L"LEARNED TRACKS"', 'L"ROUTED TRACKS"')
replace_once(
    "            const size_t idx = static_cast<size_t> (item.routeIndex - 1);\n"
    "            if (!everActive[idx].load (std::memory_order_relaxed))\n"
    "                continue;\n"
    "            if (shouldHideAsFxVisualReturn (item.routeIndex))\n"
    "                continue;\n"
    "            DrawTrack d;\n"
    "            d.meta = &item;",
    "            const size_t idx = static_cast<size_t> (item.routeIndex - 1);\n"
    "            DrawTrack d;\n"
    "            d.meta = &item;",
    "stable routed sidebar membership",
)

# FX labels are intentionally removed from the sidebar because classifier confidence
# is allowed to evolve. The list itself should be names/routes, not a changing diagnosis.
replace_once(
    "            float rowReverb = 0.0f, rowDelay = 0.0f;\n"
    "            fxAmountsForSource (item.routeIndex, rowReverb, rowDelay);\n"
    "            if (rowReverb > 0.010f) display += \"  +REV\";\n"
    "            if (rowDelay > 0.010f) display += \"  +DLY\";\n"
    "            if (isFxReturnRoute (item.routeIndex))\n"
    "                display += \"  [FX RETURN]\";\n",
    "",
    "remove dynamic FX suffixes from stable sidebar",
)

# A routed row can be not-yet-learned, so do not show a meaningless changing -120 dB.
# Use a fixed READY/WAIT state instead; the sidebar is identity/status, not a meter.
replace_once(
    "            wchar_t peakText[32] {};\n"
    "            swprintf_s (peakText, L\"%.0f\", track.peakDb);\n"
    "            RECT peakRect {sidebarRight - 45, y, sidebarRight, y + 26};\n"
    "            SetTextColor (dc, RGB (119, 219, 160));\n"
    "            DrawTextW (dc, peakText, -1, &peakRect, DT_RIGHT | DT_SINGLELINE | DT_VCENTER);",
    "            const bool learned = routeProfileReady[static_cast<size_t> (item.routeIndex - 1)].load (std::memory_order_relaxed);\n"
    "            const wchar_t* stateText = learned ? L\"READY\" : L\"WAIT\";\n"
    "            RECT stateRect {sidebarRight - 52, y, sidebarRight, y + 26};\n"
    "            SetTextColor (dc, learned ? RGB (119, 219, 160) : RGB (124, 139, 155));\n"
    "            DrawTextW (dc, stateText, -1, &stateRect, DT_RIGHT | DT_SINGLELINE | DT_VCENTER);",
    "stable sidebar status",
)

text = text.replace(
    "Web-style learned bodies: geometry is an 82nd-percentile long-term profile; live audio only changes presence.",
    "Learned bodies stay geometrically fixed; live audio only fades presence. Routed track list is session-stable."
)

out.write_text(text, encoding="utf-8")
print(out)
