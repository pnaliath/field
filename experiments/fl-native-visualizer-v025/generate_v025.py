from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v024 = root / "fl-native-visualizer-v024"

# Start from compile-green V0.24 calibration build.
runpy.run_path(str(v024 / "generate_v024.py"), run_name="__main__")
src = v024 / "generated" / "fieldv024.cpp"
out = here / "generated" / "fieldv025.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.25 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.25 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.25 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


def replace_function(signature: str, replacement: str, label: str) -> None:
    global text
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"V0.25 could not find function: {label}")
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f"V0.25 could not find opening brace: {label}")
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
        raise RuntimeError(f"V0.25 could not find closing brace: {label}")
    text = text[:start] + replacement + text[end:]


# Identity.
text = text.replace("Field V0.24", "Field V0.25")
text = text.replace("FieldV024", "FieldV025")
text = text.replace("V024", "V025")
text = text.replace("v024", "v025")
text = text.replace("FieldV024_diagnostics.csv", "FieldV025_diagnostics.csv")
text = text.replace("AXIS SENSITIVITY CALIBRATION", "EVENT SNAPSHOTS")

# User-calibrated defaults. Keep the knobs for another test pass, but boot at the
# values selected in V0.24.
text = text.replace("float xAxisSensitivity = 1.0f;", "float xAxisSensitivity = 1.25f;", 1)
text = text.replace("float zAxisSensitivity = 1.0f;", "float zAxisSensitivity = 1.70f;", 1)

# Render copies can override route presence and suppress duplicate labels/FX.
replace_once(
    "    int spatialVoiceCount = 1;\n",
    "    int spatialVoiceCount = 1;\n"
    "    bool eventSnapshot = false;\n"
    "    float visualPresenceOverride = -1.0f;\n"
    "    bool renderLabel = true;\n"
    "    bool renderFxAura = true;\n",
    "DrawTrack event render fields",
)

# Per-route transient visual snapshots. Audio thread publishes raw pan + event
# level only; sensitivity mapping stays on the UI/render side, avoiding races with
# the calibration knobs.
replace_once(
    "    std::array<std::atomic<float>, kMaxRoutes> routeSpatialPanShift;\n",
    "    std::array<std::atomic<float>, kMaxRoutes> routeSpatialPanShift;\n"
    "    static constexpr int kVisualEventSlots = 4;\n"
    "    std::array<std::array<std::atomic<float>, kVisualEventSlots>, kMaxRoutes> visualEventPan;\n"
    "    std::array<std::array<std::atomic<float>, kVisualEventSlots>, kMaxRoutes> visualEventLevelDb;\n"
    "    std::array<std::array<std::atomic<unsigned long long>, kVisualEventSlots>, kMaxRoutes> visualEventBornMs;\n"
    "    std::array<int, kMaxRoutes> visualEventWrite {};\n",
    "event snapshot state",
)
replace_once(
    "        for (auto& p : routeSpatialPanShift) p.store (0.0f, std::memory_order_relaxed);",
    "        for (auto& p : routeSpatialPanShift) p.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& route : visualEventPan) for (auto& v : route) v.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& route : visualEventLevelDb) for (auto& v : route) v.store (-120.0f, std::memory_order_relaxed);\n"
    "        for (auto& route : visualEventBornMs) for (auto& v : route) v.store (0ull, std::memory_order_relaxed);",
    "event snapshot initialization",
)

# Snapshot capture. For an established L/R transient split, a new onset invalidates
# the prior side immediately: only the currently sounding side remains visible.
# Single-position sources may retain up to four recent LEVEL snapshots so a quiet
# hit and a loud next hit appear at two Z positions instead of travelling between.
capture_helper = r'''    void captureVisualEvent (size_t routeIndex, float blockPan, float fastRms)
    {
        if (routeIndex >= kMaxRoutes || fastRms <= 1.0e-8f)
            return;
        const unsigned long long now = GetTickCount64 ();
        const float levelDb = linearToDb (std::max (1.0e-9f, fastRms));
        const int voices = std::clamp (spatialVoiceCount[routeIndex].load (std::memory_order_acquire), 1, 2);

        if (voices >= 2)
        {
            // Alternating/split hats: never leave the opposite learned anchor lit.
            for (int s = 0; s < kVisualEventSlots; ++s)
                visualEventBornMs[routeIndex][static_cast<size_t> (s)].store (0ull, std::memory_order_release);
            visualEventWrite[routeIndex] = 0;
        }

        int slot = -1;
        if (voices <= 1)
        {
            // Refresh an almost-identical event instead of creating visual clutter.
            for (int s = 0; s < kVisualEventSlots; ++s)
            {
                const auto born = visualEventBornMs[routeIndex][static_cast<size_t> (s)].load (std::memory_order_acquire);
                if (born == 0ull || now - born > 440ull)
                    continue;
                const float oldPan = visualEventPan[routeIndex][static_cast<size_t> (s)].load (std::memory_order_relaxed);
                const float oldDb = visualEventLevelDb[routeIndex][static_cast<size_t> (s)].load (std::memory_order_relaxed);
                if (std::abs (oldPan - blockPan) < 0.10f && std::abs (oldDb - levelDb) < 4.0f)
                {
                    slot = s;
                    break;
                }
            }
        }
        if (slot < 0)
        {
            slot = visualEventWrite[routeIndex];
            visualEventWrite[routeIndex] = (visualEventWrite[routeIndex] + 1) % kVisualEventSlots;
        }

        visualEventPan[routeIndex][static_cast<size_t> (slot)].store (
            std::clamp (blockPan, -1.0f, 1.0f), std::memory_order_relaxed);
        visualEventLevelDb[routeIndex][static_cast<size_t> (slot)].store (levelDb, std::memory_order_relaxed);
        // Publish timestamp last.
        visualEventBornMs[routeIndex][static_cast<size_t> (slot)].store (now, std::memory_order_release);
    }

'''
replace_once(
    "    void updateSpatialVoices (size_t routeIndex, float blockPan, float fastRms)\n    {",
    capture_helper + "    void updateSpatialVoices (size_t routeIndex, float blockPan, float fastRms)\n    {",
    "event snapshot capture helper",
)
replace_once(
    "        spatialLastOnsetMs[routeIndex] = now;\n\n        const int write = spatialEventWrite[routeIndex];",
    "        spatialLastOnsetMs[routeIndex] = now;\n"
    "        captureVisualEvent (routeIndex, blockPan, fastRms);\n\n"
    "        const int write = spatialEventWrite[routeIndex];",
    "capture visual event on onset",
)

# Snapshot opacity is independent of the route's newer envelope. That lets a prior
# quiet hit keep fading in its old position while the next loud hit appears at a
# new position.
presence_function = r'''    float visualPresenceForTrack (const DrawTrack& track) const
    {
        if (track.visualPresenceOverride >= 0.0f)
            return clamp01 (track.visualPresenceOverride);
        if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
            return 0.0f;
        return clamp01 (routeVisualPresence[static_cast<size_t> (track.meta->routeIndex - 1)].load (
            std::memory_order_relaxed));
    }
'''
replace_function(
    "    float visualPresenceForTrack (const DrawTrack& track) const",
    presence_function,
    "snapshot-aware visual presence",
)

# Avoid repeated labels / FX shells when two level snapshots briefly coexist.
replace_once(
    "    void drawTrackNameOnBody (HDC dc, const DrawTrack& track, const RECT& area)\n    {\n        if (!track.meta)",
    "    void drawTrackNameOnBody (HDC dc, const DrawTrack& track, const RECT& area)\n"
    "    {\n"
    "        if (!track.renderLabel)\n"
    "            return;\n"
    "        if (!track.meta)",
    "suppress duplicate snapshot labels",
)
replace_once(
    "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)\n    {",
    "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)\n"
    "    {\n"
    "        if (!track.renderFxAura)\n"
    "            return;",
    "suppress duplicate snapshot FX",
)

# Render topology. Learned L/R centres remain classification metadata only. They
# are NOT permanent bodies. Recent onsets produce event bodies at the CURRENT raw
# pan and instantaneous level. An old split route hard-panned later therefore
# renders one body at the new pan, not two stale anchors.
event_expand = r'''        std::vector<DrawTrack> spatialActive;
        spatialActive.reserve (active.size () * 4u);
        const unsigned long long visualNow = GetTickCount64 ();
        for (const auto& sourceTrack : active)
        {
            if (!sourceTrack.meta || sourceTrack.meta->routeIndex < 1 || sourceTrack.meta->routeIndex > kMaxRoutes)
                continue;
            const size_t idx = static_cast<size_t> (sourceTrack.meta->routeIndex - 1);
            const int voices = std::clamp (spatialVoiceCount[idx].load (std::memory_order_acquire), 1, 2);
            const float livePan = routeLivePan[idx].load (std::memory_order_relaxed);
            const float liveWidth = routeLiveWidth[idx].load (std::memory_order_relaxed);

            struct RecentEvent { int slot; unsigned long long born; float pan; float levelDb; };
            std::array<RecentEvent, kVisualEventSlots> recent {};
            int recentCount = 0;
            int newestSlot = -1;
            unsigned long long newestBorn = 0ull;
            for (int s = 0; s < kVisualEventSlots; ++s)
            {
                const auto born = visualEventBornMs[idx][static_cast<size_t> (s)].load (std::memory_order_acquire);
                if (born == 0ull || visualNow < born || visualNow - born >= 440ull)
                    continue;
                RecentEvent ev;
                ev.slot = s;
                ev.born = born;
                ev.pan = visualEventPan[idx][static_cast<size_t> (s)].load (std::memory_order_relaxed);
                ev.levelDb = visualEventLevelDb[idx][static_cast<size_t> (s)].load (std::memory_order_relaxed);
                recent[static_cast<size_t> (recentCount++)] = ev;
                if (born >= newestBorn) { newestBorn = born; newestSlot = s; }
            }

            if (recentCount > 0)
            {
                // A split source publishes only one current-side event; a single-position
                // source can briefly show multiple LEVEL locations (quiet + loud hit).
                for (int r = 0; r < recentCount; ++r)
                {
                    const auto& ev = recent[static_cast<size_t> (r)];
                    const float ageMs = static_cast<float> (visualNow - ev.born);
                    const float fade = ageMs <= 90.0f ? 1.0f :
                        clamp01 (1.0f - (ageMs - 90.0f) / 350.0f);
                    if (fade <= 0.01f)
                        continue;

                    DrawTrack d = sourceTrack;
                    d.eventSnapshot = true;
                    d.visualPresenceOverride = fade;
                    d.renderLabel = ev.slot == newestSlot;
                    d.renderFxAura = ev.slot == newestSlot;
                    d.spatialVoiceIndex = 0;
                    d.spatialVoiceCount = voices >= 2 ? 2 : 1;
                    d.balance = std::clamp (ev.pan * xAxisSensitivity, -1.0f, 1.0f);
                    d.width = liveWidth;

                    const float backness = clamp01 ((-14.0f - ev.levelDb) / 58.0f);
                    const float baseDepth = 0.10f + backness * 0.72f;
                    d.visualZ = std::clamp (
                        0.46f + (baseDepth - 0.46f) * zAxisSensitivity, 0.08f, 0.84f);
                    const float frontness = 1.0f - backness;
                    d.volumeThickness = 0.040f + frontness * 0.075f;
                    spatialActive.push_back (d);
                }
                continue;
            }

            // No recent hit: never resurrect both learned L/R anchors. A sustained
            // or later hard-panned signal gets one body at the CURRENT live pan.
            DrawTrack d = sourceTrack;
            d.spatialVoiceIndex = 0;
            d.spatialVoiceCount = voices >= 2 ? 2 : 1;
            d.balance = std::clamp (livePan * xAxisSensitivity, -1.0f, 1.0f);
            d.width = liveWidth;
            spatialActive.push_back (d);
        }
        active = std::move (spatialActive);

'''
replace_between(
    "        std::vector<DrawTrack> spatialActive;",
    "        // V0.23 absolute depth from active source RMS.",
    event_expand,
    "event-driven spatial render expansion",
)

# Base/sustained tracks still use the normal depth smoother. Event snapshots skip
# this loop completely: their Z is immutable for their lifetime, so there is no
# animated travel from a quiet hit to a loud hit.
depth_block = r'''        // V0.25 sustained-source depth. Event snapshots already carry an immutable Z.
        for (auto& track : active)
        {
            if (track.eventSnapshot)
                continue;
            if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
                continue;
            const size_t idx = static_cast<size_t> (track.meta->routeIndex - 1);
            float levelDb = routeDepthLevelDb[idx].load (std::memory_order_relaxed);
            if (levelDb <= -119.0f)
                levelDb = -48.0f;

            const float backness = clamp01 ((-14.0f - levelDb) / 58.0f);
            const float baseDepth = 0.10f + backness * 0.72f;
            const float targetDepth = std::clamp (
                0.46f + (baseDepth - 0.46f) * zAxisSensitivity, 0.08f, 0.84f);
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
    "        // V0.23 absolute depth from active source RMS.",
    "        std::vector<DrawTrack> renderOrder = active;",
    depth_block,
    "immutable event Z depth",
)

# Diagnostics: preserve selected sensitivity values in existing columns; update banner.
text = text.replace(
    "V0.24 calibration: X SENS and Z SENS are test-only render mapping controls",
    "V0.25 event snapshots: immutable hit Z + current-side-only split rendering"
)

out.write_text(text, encoding="utf-8")
print(out)
