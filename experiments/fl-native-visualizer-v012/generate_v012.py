from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v011_dir = root / "fl-native-visualizer-v011"

runpy.run_path(str(v011_dir / "generate_v011.py"), run_name="__main__")
src = v011_dir / "generated" / "fieldv011.cpp"
out = here / "generated" / "fieldv012.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.12 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.12 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.12 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


# Fresh FL-native identity.
text = text.replace("Field V0.11 Room Space Visualizer", "Field V0.12 Complete Room Tracking")
text = text.replace("FieldV011", "FieldV012")
text = text.replace("V0.11", "V0.12")
text = text.replace("V011", "V012")

# -----------------------------------------------------------------------------
# 1) Correct the in-DAW reported visual direction inversions.
# FL's native input channel ordering in this probe presents stereo balance with
# the opposite sign to the room display, so invert the visual DrawTrack balance.
# Frequency height is inverted as reported by the V0.11 room test as well.
# This changes visualization only; reconstruction/audio samples are untouched.
text = text.replace(
    "d.balance = routeBalance[idx].load (std::memory_order_relaxed);",
    "d.balance = -routeBalance[idx].load (std::memory_order_relaxed);"
)
replace_once(
    "        return 0.06f + t * 0.96f;",
    "        return 0.06f + (1.0f - t) * 0.96f;",
    "invert frequency room Y",
)

# -----------------------------------------------------------------------------
# 2) Make muted FL colours visibly distinct without inventing a new palette.
# Expand each colour's RGB chroma around its own mean and modestly increase
# luminance contrast. Hue identity remains derived from the FL mixer colour.
colour_helper = r'''
COLORREF enhanceMixerColor (COLORREF raw)
{
    if (raw == RGB (0, 0, 0))
        return RGB (90, 155, 205);

    float r = static_cast<float> (GetRValue (raw));
    float g = static_cast<float> (GetGValue (raw));
    float b = static_cast<float> (GetBValue (raw));
    const float mean = (r + g + b) / 3.0f;
    constexpr float chromaGain = 3.15f;
    r = mean + (r - mean) * chromaGain;
    g = mean + (g - mean) * chromaGain;
    b = mean + (b - mean) * chromaGain;

    // Preserve the source brightness ordering, but open the visual contrast.
    const float lum = (r + g + b) / 3.0f;
    const float targetLum = std::clamp (128.0f + (lum - 128.0f) * 1.18f, 58.0f, 218.0f);
    const float delta = targetLum - lum;
    r += delta; g += delta; b += delta;

    return RGB (
        std::clamp (static_cast<int> (std::lround (r)), 24, 242),
        std::clamp (static_cast<int> (std::lround (g)), 24, 242),
        std::clamp (static_cast<int> (std::lround (b)), 24, 242));
}

'''
replace_once(
    "void analyseStereo (PWAV32FS buffer, int length, float& rmsDb, float& peakDb)\n{",
    colour_helper + "void analyseStereo (PWAV32FS buffer, int length, float& rmsDb, float& peakDb)\n{",
    "enhanced mixer colour helper",
)
text = text.replace(
    "COLORREF raw = static_cast<COLORREF> (track.meta->color & 0x00FFFFFF);",
    "COLORREF raw = enhanceMixerColor (static_cast<COLORREF> (track.meta->color & 0x00FFFFFF));"
)
text = text.replace(
    "COLORREF raw = static_cast<COLORREF> (item.color & 0x00FFFFFF);",
    "COLORREF raw = enhanceMixerColor (static_cast<COLORREF> (item.color & 0x00FFFFFF));"
)

# -----------------------------------------------------------------------------
# 3) FX classification may classify a route, but only strong, source-associated
# temporal evidence is allowed to remove a primary spectral body. This keeps
# rhythmic instruments from disappearing merely because they correlate with
# another track. Named FX returns need less evidence; unnamed returns still work
# once their audio-derived evidence becomes strong enough.
visual_fx_gate = r'''
    bool shouldHideAsFxVisualReturn (int route) const
    {
        if (!isFxReturnRoute (route) || route < 1 || route > kMaxRoutes)
            return false;

        const size_t idx = static_cast<size_t> (route - 1);
        const float confidence = fxReturnConfidence[idx];
        float bestLink = 0.0f;
        bool hasValidSource = false;
        for (const auto& link : fxLinks)
        {
            if (link.returnRoute != route)
                continue;
            if (link.sourceRoute < 1 || link.sourceRoute > kMaxRoutes || link.sourceRoute == route)
                continue;
            bestLink = std::max (bestLink, link.score);
            hasValidSource = true;
        }
        if (!hasValidSource)
            return false;

        const bool hinted = temporalNameHint (route) != 0;
        const float confidenceNeeded = hinted ? 0.69f : 0.90f;
        const float linkNeeded = hinted ? 0.30f : 0.58f;
        return confidence >= confidenceNeeded && bestLink >= linkNeeded;
    }

'''
replace_once(
    "    void fxAmountsForSource",
    visual_fx_gate + "    void fxAmountsForSource",
    "conservative visual FX-return gate",
)

# -----------------------------------------------------------------------------
# 4) Separate 'all learned audio routes' from 'primary bodies'. Sidebar/list
# always uses allLearned in FL mixer order. Only high-confidence FX returns are
# suppressed as standalone bodies. Once a route crosses the existence floor it
# never disappears from this plugin session just because the current note stops.
primary_builder = r'''        std::vector<DrawTrack> allLearned;
        std::vector<DrawTrack> active;
        allLearned.reserve (inputs.size ());
        active.reserve (inputs.size ());
        for (const auto& item : inputs)
        {
            if (item.routeIndex < 1 || item.routeIndex > kMaxRoutes)
                continue;
            const size_t idx = static_cast<size_t> (item.routeIndex - 1);
            const float peak = routePeakDb[idx].load (std::memory_order_relaxed);
            if (!everActive[idx].load (std::memory_order_relaxed))
                continue;

            DrawTrack d;
            d.meta = &item;
            d.peakDb = peak;
            d.balance = -routeBalance[idx].load (std::memory_order_relaxed);
            d.width = routeWidth[idx].load (std::memory_order_relaxed);
            allLearned.push_back (d);

            if (!shouldHideAsFxVisualReturn (item.routeIndex))
                active.push_back (d);
        }

'''
replace_between(
    "        std::vector<DrawTrack> active;\n",
    "        if (active.empty ())",
    primary_builder,
    "all-learned vs primary route builder",
)

# The V0.09 safety fallback remains after the builder. It now uses the corrected
# visual pan sign via the global replacement above.
replace_once(
    "        std::vector<DrawTrack> stableList = active;",
    "        std::vector<DrawTrack> stableList = allLearned;",
    "sidebar shows all learned routes",
)

# -----------------------------------------------------------------------------
# 5) Multiple sources can occupy almost the same real X/Y/Z coordinates. After
# physically depth-sorted volume rendering, draw a thin identity trace for every
# primary object. It does not move the object; it only prevents a nearer opaque
# GDI volume from making every farther source visually indistinguishable.
identity_trace = r'''
    void drawIdentityTrace (HDC dc, const DrawTrack& track, const RECT& area)
    {
        if (!track.meta)
            return;
        const float halfDepth = std::clamp (track.volumeThickness * 0.5f, 0.018f, 0.10f);
        const float zFront = std::clamp (track.visualZ - halfDepth, 0.01f, 0.98f);
        const auto front = projectedBodyPointsAtDepth (track, area, zFront);
        COLORREF raw = enhanceMixerColor (static_cast<COLORREF> (track.meta->color & 0x00FFFFFF));
        const COLORREF line = mixColor (raw, RGB (248, 251, 255), 0.18f);
        HPEN pen = CreatePen (PS_SOLID, 1, line);
        auto oldPen = SelectObject (dc, pen);
        auto oldBrush = SelectObject (dc, GetStockObject (NULL_BRUSH));
        Polygon (dc, front.data (), static_cast<int> (front.size ()));
        const auto a = projectWorld (track.balance, 0.12f, zFront, area);
        const auto b = projectWorld (track.balance, 0.96f, zFront, area);
        MoveToEx (dc, a.x, a.y, nullptr); LineTo (dc, b.x, b.y);
        SelectObject (dc, oldBrush);
        SelectObject (dc, oldPen);
        DeleteObject (pen);
    }

'''
replace_once(
    "    void paint (HWND hwnd)",
    identity_trace + "    void paint (HWND hwnd)",
    "identity trace renderer",
)

old_render = '''        for (const auto& track : renderOrder)
        {
            float reverbAmount = 0.0f, delayAmount = 0.0f;
            fxAmountsForSource (track.meta ? track.meta->routeIndex : 0, reverbAmount, delayAmount);
            drawFxAura (dc, track, fieldArea, reverbAmount, delayAmount);
            drawSpectralBody (dc, track, fieldArea);
        }'''
new_render = '''        for (const auto& track : renderOrder)
        {
            float reverbAmount = 0.0f, delayAmount = 0.0f;
            fxAmountsForSource (track.meta ? track.meta->routeIndex : 0, reverbAmount, delayAmount);
            drawFxAura (dc, track, fieldArea, reverbAmount, delayAmount);
            drawSpectralBody (dc, track, fieldArea);
        }
        // Readability overlay only; object positions remain their inferred room coordinates.
        for (const auto& track : renderOrder)
            drawIdentityTrace (dc, track, fieldArea);'''
replace_once(old_render, new_render, "multi-object identity trace pass")

# Clarify what the list count means in this build.
text = text.replace(
    "Room view from the mix position. X=pan, Y=frequency, Z=apparent acoustic depth; objects are true extruded spectral volumes.",
    "Room view with persistent learned routes. Primary bodies remain independent; high-confidence temporal returns attach as ambience layers."
)

out.write_text(text, encoding="utf-8")
print(out)
