from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v031 = root / "fl-native-visualizer-v031"

runpy.run_path(str(v031 / "generate_v031.py"), run_name="__main__")
src = v031 / "generated" / "fieldv031.cpp"
out = here / "generated" / "fieldv032.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.32 could not find patch point: {label}")
    text = text.replace(old, new, 1)


# Identity.
text = text.replace("Field V0.31", "Field V0.32")
text = text.replace("FieldV031", "FieldV032")
text = text.replace("V031", "V032")
text = text.replace("v031", "v032")
text = text.replace("FieldV031_diagnostics.csv", "FieldV032_diagnostics.csv")
text = text.replace("STABLE DUAL VOICES", "INSTANT STABLE SHAPE")

# -----------------------------------------------------------------------------
# Per-source held depth. Z is sampled when a new sounding segment begins and then
# remains immutable until that segment ends. This removes continuous front/back
# swimming while preserving a different Z for the next materially different hit.
replace_once(
    "    std::array<float, kMaxRoutes> routeStablePairShift {};\n",
    "    std::array<float, kMaxRoutes> routeStablePairShift {};\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeHeldDepthDb;\n"
    "    std::array<std::atomic<bool>, kMaxRoutes> routeDepthSegmentActive;\n",
    "held depth state",
)

replace_once(
    "        for (auto& v : routeSustainedVisual) v.store (false, std::memory_order_relaxed);",
    "        for (auto& v : routeSustainedVisual) v.store (false, std::memory_order_relaxed);\n"
    "        for (auto& v : routeHeldDepthDb) v.store (-48.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : routeDepthSegmentActive) v.store (false, std::memory_order_relaxed);",
    "held depth init",
)

# Capture the segment depth once. We use the current fast RMS at the first valid
# signal block. No later block in the same note/hit can drag the body in Z.
replace_once(
    "            const bool hasSignal = targetPeakDb > -114.0f;\n",
    "            const bool hasSignal = targetPeakDb > -114.0f;\n"
    "            const bool wasDepthActive = routeDepthSegmentActive[routeArrayIndex].load (std::memory_order_relaxed);\n"
    "            if (hasSignal && !wasDepthActive)\n"
    "            {\n"
    "                const float segmentDb = linearToDb (std::max (1.0e-9f, static_cast<float> (fastRms)));\n"
    "                routeHeldDepthDb[routeArrayIndex].store (segmentDb, std::memory_order_relaxed);\n"
    "                routeDepthSegmentActive[routeArrayIndex].store (true, std::memory_order_release);\n"
    "            }\n"
    "            else if (!hasSignal && wasDepthActive)\n"
    "                routeDepthSegmentActive[routeArrayIndex].store (false, std::memory_order_release);\n",
    "capture immutable segment Z",
)

# Sustained/base depth uses the held segment value, not continuously smoothed live RMS.
text = text.replace(
    "            float levelDb = routeDepthLevelDb[idx].load (std::memory_order_relaxed);",
    "            float levelDb = routeHeldDepthDb[idx].load (std::memory_order_relaxed);",
)
# Kill the inherited Z interpolator: position snaps to the segment's selected plane
# and remains there. Event snapshots already have immutable Z.
text = text.replace(
    "            float& smoothDepth = spatialDepth[idx];\n            if (smoothDepth <= 0.001f)\n                smoothDepth = targetDepth;\n            else\n                smoothDepth += (targetDepth - smoothDepth) * 0.075f;\n            track.visualZ = std::clamp (smoothDepth, 0.08f, 0.84f);",
    "            spatialDepth[idx] = targetDepth;\n            track.visualZ = std::clamp (targetDepth, 0.08f, 0.84f);",
)

# -----------------------------------------------------------------------------
# Rare/one-shot sounds must get a useful body on their FIRST valid full FFT frame.
# V0.30 waited 16 analysis frames, so occasional sounds could never converge.
# Instead sanitize the first frame against its own peak (removing broadband leakage)
# and publish immediately. Frames 2-4 refine quickly; after that identity adapts
# extremely slowly so lobe topology cannot flicker around the gate.
old_display = '''        constexpr unsigned int kDisplayWarmupFrames = 16u;
        if (routeProfileFrames[routeIndex] >= kDisplayWarmupFrames)
        {
            const bool wasReady = routeDisplayProfileReady[routeIndex].load (std::memory_order_relaxed);
            for (int band = 0; band < kBands; ++band)
            {
                auto& cell = routeDisplayProfileDb[routeIndex][static_cast<size_t> (band)];
                const float targetDb = smoothDb[static_cast<size_t> (band)];
                if (!wasReady)
                    cell.store (targetDb, std::memory_order_relaxed);
                else
                {
                    const float oldDb = cell.load (std::memory_order_relaxed);
                    cell.store (oldDb + (targetDb - oldDb) * 0.012f, std::memory_order_relaxed);
                }
            }
            routeDisplayProfileReady[routeIndex].store (true, std::memory_order_release);
        }'''
new_display = '''        constexpr unsigned int kDisplayWarmupFrames = 1u;
        if (routeProfileFrames[routeIndex] >= kDisplayWarmupFrames)
        {
            const bool wasReady = routeDisplayProfileReady[routeIndex].load (std::memory_order_relaxed);
            float displayPeakDb = -120.0f;
            for (float db : smoothDb)
                displayPeakDb = std::max (displayPeakDb, db);

            std::array<float, kBands> sanitizedDb {};
            for (int band = 0; band < kBands; ++band)
            {
                const float db = smoothDb[static_cast<size_t> (band)];
                const float left = smoothDb[static_cast<size_t> (std::max (0, band - 1))];
                const float right = smoothDb[static_cast<size_t> (std::min (kBands - 1, band + 1))];
                const bool nearPeak = db >= displayPeakDb - 38.0f;
                const bool neighbourSupport = std::max (left, right) >= displayPeakDb - 42.0f;
                sanitizedDb[static_cast<size_t> (band)] = (nearPeak && neighbourSupport) ? db : -120.0f;
            }

            const float alpha = !wasReady ? 1.0f :
                (routeProfileFrames[routeIndex] <= 4u ? 0.35f : 0.0025f);
            for (int band = 0; band < kBands; ++band)
            {
                auto& cell = routeDisplayProfileDb[routeIndex][static_cast<size_t> (band)];
                const float targetDb = sanitizedDb[static_cast<size_t> (band)];
                if (!wasReady)
                    cell.store (targetDb, std::memory_order_relaxed);
                else
                {
                    const float oldDb = cell.load (std::memory_order_relaxed);
                    cell.store (oldDb + (targetDb - oldDb) * alpha, std::memory_order_relaxed);
                }
            }
            routeDisplayProfileReady[routeIndex].store (true, std::memory_order_release);
        }'''
replace_once(old_display, new_display, "instant sanitized display profile")

# -----------------------------------------------------------------------------
# Presence: remove threshold chatter. Once a visible object is present, let it decay
# smoothly through the calibrated 500 ms visual tail rather than toggling at tiny
# block gaps. Attack is quick but not a one-frame flash.
text = text.replace("targetPresence > oldPresence ? 0.24f : 0.010f", "targetPresence > oldPresence ? 0.18f : 0.0045f", 1)
text = text.replace("std::exp (-blockMs / 360.0f)", "std::exp (-blockMs / 500.0f)", 1)

# Event-snapshot fading itself remains the user-calibrated 500 ms. Keep geometry
# immutable for the entire fade and do not let base route presence resurrect it.

text = text.replace(
    "V0.31: sustained discrete L/R stays two stable bodies; transient L/R stays current-hit only",
    "V0.32: first-frame sanitized identity + frozen per-segment Z + low-flicker presence"
)

out.write_text(text, encoding="utf-8")
print(out)
