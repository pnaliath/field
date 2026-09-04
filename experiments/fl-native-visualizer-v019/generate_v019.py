from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v018 = root / "fl-native-visualizer-v018"

# Start from the compile-green diagnostics build so the same CSV can verify fixes.
runpy.run_path(str(v018 / "generate_v018.py"), run_name="__main__")
src = v018 / "generated" / "fieldv018.cpp"
out = here / "generated" / "fieldv019.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.19 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.19 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.19 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


# Fresh plugin identity and diagnostics filename.
text = text.replace("Field V0.18", "Field V0.19")
text = text.replace("FieldV018", "FieldV019")
text = text.replace("V018", "V019")
text = text.replace("v018", "v019")
text = text.replace("FieldV018_diagnostics.csv", "FieldV019_diagnostics.csv")
text = text.replace("RESPONSE DIAGNOSTICS", "MEASURED RESPONSE FIXES")

# -----------------------------------------------------------------------------
# 1) Presence must decay on EVERY audio block, even when FL does not mark a route
# IO_Filled. V0.18 diagnostics proved this was the main frozen-shape bug.
# Use a time-constant, not a block-count constant, so behaviour is buffer-size-safe.
presence_decay = r'''        // V0.19: global visual decay runs before GetInBuffer/IO_Filled gating.
        // This prevents a route's last presence value freezing when FL stops supplying
        // a filled buffer during rests/pauses.
        {
            const float blockMs = std::max (0.1f, diagBlockMs.load (std::memory_order_relaxed));
            const float releaseCoeff = std::exp (-blockMs / 145.0f);
            for (int route = 0; route < count; ++route)
            {
                const size_t idx = static_cast<size_t> (route);
                if (routePresenceHoldBlocks[idx] > 0)
                {
                    --routePresenceHoldBlocks[idx];
                    continue;
                }
                auto& p = routeVisualPresence[idx];
                const float oldPresence = p.load (std::memory_order_relaxed);
                if (oldPresence > 0.0001f)
                    p.store (oldPresence * releaseCoeff, std::memory_order_relaxed);
            }
        }

'''
replace_once(
    "        const bool doSpectrum = ((++analysisBlockCounter & 3u) == 0u);",
    presence_decay + "        const bool doSpectrum = ((++analysisBlockCounter & 3u) == 0u);",
    "global presence decay",
)

# The per-filled-route block used to own the hold countdown as well. Since the
# global pass now owns it, keep only the target hold behaviour here.
text = text.replace(
    "                else if (routePresenceHoldBlocks[routeArrayIndex] > 0)\n"
    "                {\n"
    "                    --routePresenceHoldBlocks[routeArrayIndex];\n"
    "                    targetPresence = std::max (targetPresence, oldPresence * 0.94f);\n"
    "                }",
    "                else if (routePresenceHoldBlocks[routeArrayIndex] > 0)\n"
    "                    targetPresence = std::max (targetPresence, oldPresence * 0.94f);"
)

# -----------------------------------------------------------------------------
# 2) FX-return suppression becomes deliberately conservative. A named/hinted
# return can still attach normally. An unnamed return must have near-certain
# repeated evidence before it is allowed to hide a primary body. This prevents
# multi-second missed instruments measured in V0.18.
fx_gate = r'''    bool shouldHideAsFxVisualReturn (int route) const
    {
        if (!isFxReturnRoute (route) || route < 1 || route > kMaxRoutes)
            return false;

        const size_t idx = static_cast<size_t> (route - 1);
        float bestLink = 0.0f;
        bool validSource = false;
        for (const auto& link : fxLinks)
        {
            if (link.returnRoute != route || link.sourceRoute < 1 ||
                link.sourceRoute > kMaxRoutes || link.sourceRoute == route)
                continue;
            bestLink = std::max (bestLink, link.score);
            validSource = true;
        }
        if (!validSource)
            return false;

        const float confidence = fxReturnConfidence[idx];
        const bool hinted = temporalNameHint (route) != 0;

        // Explicit/obvious AUX/REV/DLY returns can attach with strong evidence.
        if (hinted)
            return confidence >= 0.80f && bestLink >= 0.38f;

        // Generic unnamed returns are still supported, but only when evidence is
        // overwhelmingly return-like. False positives therefore remain visible.
        return confidence >= 0.985f && bestLink >= 0.82f;
    }

'''
replace_between(
    "    bool shouldHideAsFxVisualReturn (int route) const\n    {",
    "    void fxAmountsForSource",
    fx_gate,
    "conservative FX visual suppression",
)

# -----------------------------------------------------------------------------
# 3) First visible response should not wait unnecessarily for the long-term shape
# learner. Four profile observations are enough for a provisional body (~80 ms in
# the measured session); the 82nd-percentile profile keeps learning afterward.
replace_once(
    "constexpr int kProfileMinFrames = 8;",
    "constexpr int kProfileMinFrames = 4;",
    "faster provisional profile readiness",
)

# -----------------------------------------------------------------------------
# 4) Occupancy gate: the previous 76 dB range admitted Goertzel leakage/noise all
# the way from 28 Hz to 18 kHz. Use an adaptive absolute+relative floor. Quiet
# tracks still work because the absolute floor follows very quiet own peaks.
shape_energy = r'''    float learnedShapeEnergy (size_t routeIndex, int band) const
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

        // Normal material: keep roughly the strongest 34 dB of its own spectral
        // identity. Very quiet material gets an adaptive absolute floor instead of
        // being erased merely because its overall level is low.
        const float relativeFloor = ownPeakDb - 34.0f;
        const float adaptiveAbsoluteFloor = std::min (-88.0f, ownPeakDb - 18.0f);
        const float floorDb = std::max (relativeFloor, adaptiveAbsoluteFloor);
        if (spectrumDb <= floorDb)
            return 0.0f;

        // Reject weak isolated leakage: require local support in this log-frequency
        // neighbourhood. The profile is already 1-2-1 smoothed, so this remains
        // stable while removing floor-to-ceiling ghost occupancy.
        float localPeak = spectrumDb;
        if (band > 0)
            localPeak = std::max (localPeak,
                routeProfileDb[routeIndex][static_cast<size_t> (band - 1)].load (std::memory_order_relaxed));
        if (band + 1 < kBands)
            localPeak = std::max (localPeak,
                routeProfileDb[routeIndex][static_cast<size_t> (band + 1)].load (std::memory_order_relaxed));
        if (localPeak < floorDb + 1.5f)
            return 0.0f;

        const float span = std::max (6.0f, ownPeakDb - floorDb);
        return clamp01 ((spectrumDb - floorDb) / span);
    }

'''
replace_between(
    "    float learnedShapeEnergy (size_t routeIndex, int band) const\n    {",
    "    struct ProjectedPoint",
    shape_energy,
    "tight spectral occupancy",
)

# Diagnostics overlay/CSV stays enabled so this exact build can verify the fixes.
text = text.replace(
    "RAW -> PRESENCE -> LEARNED PROFILE -> Z -> DRAW",
    "V0.19 FIXED: RAW -> PRESENCE -> PROFILE -> Z -> DRAW"
)
text = text.replace(
    "Web-style lobes: occupied frequencies only, absolute per-track Z, held presence, stacked 3D rings.",
    "Measured fixes: block-safe presence decay, conservative FX suppression, tighter occupied-frequency lobes."
)

out.write_text(text, encoding="utf-8")
print(out)
