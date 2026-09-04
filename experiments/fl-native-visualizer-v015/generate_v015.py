from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v014_dir = root / "fl-native-visualizer-v014"

# Start from the latest FL-native one-instance/routing/room implementation, then
# replace its live-spectrum visual grammar with the browser prototype's learned
# long-term profile grammar from ANALYSIS.md.
runpy.run_path(str(v014_dir / "generate_v014.py"), run_name="__main__")
src = v014_dir / "generated" / "fieldv014.cpp"
out = here / "generated" / "fieldv015.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.15 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.15 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.15 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


# Fresh identity.
text = text.replace("Field V0.14 Stable Pose + Quiet Tracks", "Field V0.15 Learned Shape Visualizer")
text = text.replace("FieldV014", "FieldV015")
text = text.replace("V0.14", "V0.15")
text = text.replace("V014", "V015")

# -----------------------------------------------------------------------------
# Browser analysis contract: 76 logarithmic bands, 28 Hz -> 18 kHz, a 64-bin
# running dB histogram, 82nd percentile, and the original 76 dB shape range.
replace_once(
    "constexpr int kBands = 24;\n",
    "constexpr int kBands = 76;\n"
    "constexpr int kProfileBins = 64;\n"
    "constexpr int kProfileMinFrames = 8;\n"
    "constexpr unsigned int kProfileRenormFrames = 512;\n"
    "constexpr float kProfileMinDb = -120.0f;\n"
    "constexpr float kProfileMaxDb = 12.0f;\n"
    "constexpr float kProfilePercentile = 0.82f;\n"
    "constexpr float kShapeDynDb = 76.0f;\n"
    "constexpr float kShapeGate = 0.095f;\n",
    "web profile constants",
)

# The browser grid is 28 Hz - 18 kHz. These literals in this generated source are
# frequency-grid endpoints/labels, not audio thresholds.
text = text.replace("const float minHz = 70.0f;", "const float minHz = 28.0f;")
text = text.replace("constexpr float minHz = 70.0f;", "constexpr float minHz = 28.0f;")
text = text.replace("const float maxHz = 16000.0f;", "const float maxHz = 18000.0f;")
text = text.replace("constexpr float maxHz = 16000.0f;", "constexpr float maxHz = 18000.0f;")
text = text.replace("std::min (16000.0f, sr * 0.42f)", "std::min (18000.0f, sr * 0.42f)")
# Room tick endpoints.
text = text.replace("70.0f, 120.0f", "28.0f, 120.0f")
text = text.replace("10000.0f, 16000.0f", "10000.0f, 18000.0f")

# -----------------------------------------------------------------------------
# Learned-profile state. Histogram counters are touched only by the audio thread;
# UI-visible profiles/metrics are atomics.
replace_once(
    "    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeSpectrum;\n",
    "    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeSpectrum;\n"
    "    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeProfileDb;\n"
    "    std::array<std::array<std::array<unsigned int, kProfileBins>, kBands>, kMaxRoutes> routeProfileHistogram {};\n"
    "    std::array<unsigned int, kMaxRoutes> routeProfileFrames {};\n"
    "    std::array<unsigned int, kMaxRoutes> routeDutyFrames {};\n"
    "    std::array<unsigned int, kMaxRoutes> routeDutyActiveFrames {};\n"
    "    std::array<double, kMaxRoutes> routePanWeight {};\n"
    "    std::array<double, kMaxRoutes> routePanWeightedSum {};\n"
    "    std::array<double, kMaxRoutes> routeWidthWeightedSum {};\n"
    "    std::array<std::atomic<bool>, kMaxRoutes> routeProfileReady;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeDuty;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeLoudnessDb;\n"
    "    std::atomic<float> sessionProfilePeakDb {-120.0f};\n",
    "learned profile members",
)

# Initialise the new atomics.
replace_once(
    "        for (auto& route : routeSpectrum)\n            for (auto& band : route)\n                band.store (0.0f, std::memory_order_relaxed);",
    "        for (auto& route : routeSpectrum)\n"
    "            for (auto& band : route)\n"
    "                band.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& route : routeProfileDb)\n"
    "            for (auto& band : route)\n"
    "                band.store (-120.0f, std::memory_order_relaxed);\n"
    "        for (auto& ready : routeProfileReady)\n"
    "            ready.store (false, std::memory_order_relaxed);\n"
    "        for (auto& duty : routeDuty)\n"
    "            duty.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& loudness : routeLoudnessDb)\n"
    "            loudness.store (-120.0f, std::memory_order_relaxed);",
    "profile initialization",
)

# -----------------------------------------------------------------------------
# Long-term pan/width: accumulate energy-weighted position while signal exists.
# A note, transient or silence no longer moves an already learned object around.
old_pose = (
    "            if (hasSignal)\n"
    "            {\n"
    "                auto& balanceCell = routeBalance[routeArrayIndex];\n"
    "                const float oldBalance = balanceCell.load (std::memory_order_relaxed);\n"
    "                balanceCell.store (oldBalance + (balance - oldBalance) * 0.035f, std::memory_order_relaxed);\n\n"
    "                auto& widthCell = routeWidth[routeArrayIndex];\n"
    "                const float oldWidth = widthCell.load (std::memory_order_relaxed);\n"
    "                widthCell.store (oldWidth + (width - oldWidth) * 0.035f, std::memory_order_relaxed);\n"
    "                if (doSpectrum)\n"
    "                    analyseSpectrum (routeArrayIndex, routeBuffer, length);\n"
    "            }"
)
new_pose = (
    "            if (hasSignal)\n"
    "            {\n"
    "                const double spatialWeight = std::max (1.0e-9, left + right);\n"
    "                routePanWeight[routeArrayIndex] += spatialWeight;\n"
    "                routePanWeightedSum[routeArrayIndex] += static_cast<double> (balance) * spatialWeight;\n"
    "                routeWidthWeightedSum[routeArrayIndex] += static_cast<double> (width) * spatialWeight;\n"
    "                const double learnedWeight = std::max (1.0e-9, routePanWeight[routeArrayIndex]);\n"
    "                routeBalance[routeArrayIndex].store (\n"
    "                    static_cast<float> (routePanWeightedSum[routeArrayIndex] / learnedWeight), std::memory_order_relaxed);\n"
    "                routeWidth[routeArrayIndex].store (\n"
    "                    clamp01 (static_cast<float> (routeWidthWeightedSum[routeArrayIndex] / learnedWeight)), std::memory_order_relaxed);\n"
    "                if (doSpectrum)\n"
    "                    analyseSpectrum (routeArrayIndex, routeBuffer, length);\n"
    "            }"
)
replace_once(old_pose, new_pose, "long-term spatial pose")

# Duty-cycle observation: every learned route accrues time every block; blocks with
# real signal accrue active time. This is the streaming equivalent of the web envelope duty.
replace_once(
    "        int live = 0;\n        const bool doSpectrum = ((++analysisBlockCounter & 3u) == 0u);",
    "        int live = 0;\n"
    "        for (int route = 0; route < count; ++route)\n"
    "        {\n"
    "            const size_t idx = static_cast<size_t> (route);\n"
    "            if (everActive[idx].load (std::memory_order_relaxed))\n"
    "                ++routeDutyFrames[idx];\n"
    "        }\n"
    "        const bool doSpectrum = ((++analysisBlockCounter & 3u) == 0u);",
    "duty observation clock",
)
replace_once(
    "            if (hasSignal)\n                everActive[routeArrayIndex].store (true, std::memory_order_relaxed);",
    "            if (hasSignal)\n"
    "            {\n"
    "                everActive[routeArrayIndex].store (true, std::memory_order_relaxed);\n"
    "                ++routeDutyActiveFrames[routeArrayIndex];\n"
    "            }\n"
    "            const unsigned int dutyFrames = std::max (1u, routeDutyFrames[routeArrayIndex]);\n"
    "            routeDuty[routeArrayIndex].store (\n"
    "                clamp01 (static_cast<float> (routeDutyActiveFrames[routeArrayIndex]) / static_cast<float> (dutyFrames)),\n"
    "                std::memory_order_relaxed);",
    "duty active count",
)

# -----------------------------------------------------------------------------
# Replace the momentary per-band smoother with the browser model's streaming
# 82nd-percentile histogram. Histogram samples are taken only while this route has
# meaningful signal; duty is tracked separately above. This preserves sparse percussion
# while keeping the body stable once learned.
profile_analysis = r'''    void analyseSpectrum (size_t routeIndex, PWAV32FS buffer, int length)
    {
        if (!buffer || length <= 0 || routeIndex >= kMaxRoutes)
            return;

        std::array<float, kBands> frameDb {};
        for (int band = 0; band < kBands; ++band)
        {
            const float coeff = bandCoeff[static_cast<size_t> (band)].load (std::memory_order_relaxed);
            double s1 = 0.0;
            double s2 = 0.0;
            for (int i = 0; i < length; ++i)
            {
                const double mono = 0.5 * static_cast<double> (buffer[i][0] + buffer[i][1]);
                const double s0 = mono + static_cast<double> (coeff) * s1 - s2;
                s2 = s1;
                s1 = s0;
            }
            const double power = std::max (0.0,
                s1 * s1 + s2 * s2 - static_cast<double> (coeff) * s1 * s2);
            const double magnitude = (2.0 * std::sqrt (power)) / std::max (1, length);
            const float db = std::clamp (linearToDb (magnitude), kProfileMinDb, kProfileMaxDb);
            frameDb[static_cast<size_t> (band)] = db;

            const float t = clamp01 ((db - kProfileMinDb) / (kProfileMaxDb - kProfileMinDb));
            const int bin = std::clamp (
                static_cast<int> (std::floor (t * static_cast<float> (kProfileBins))), 0, kProfileBins - 1);
            ++routeProfileHistogram[routeIndex][static_cast<size_t> (band)][static_cast<size_t> (bin)];
        }

        ++routeProfileFrames[routeIndex];

        // Keep the histogram adaptive over long sessions: when it grows large,
        // halve every bin. This preserves the percentile while allowing upstream EQ
        // changes to become visible over a new listening pass rather than never changing.
        if (routeProfileFrames[routeIndex] >= kProfileRenormFrames)
        {
            unsigned int newTotal = 0;
            for (int band = 0; band < kBands; ++band)
            {
                unsigned int bandTotal = 0;
                for (int bin = 0; bin < kProfileBins; ++bin)
                {
                    auto& c = routeProfileHistogram[routeIndex][static_cast<size_t> (band)][static_cast<size_t> (bin)];
                    c = (c + 1u) / 2u;
                    bandTotal += c;
                }
                if (band == 0)
                    newTotal = bandTotal;
            }
            routeProfileFrames[routeIndex] = std::max (1u, newTotal);
        }

        const unsigned int total = std::max (1u, routeProfileFrames[routeIndex]);
        const unsigned int target = std::max (1u,
            static_cast<unsigned int> (std::ceil (static_cast<float> (total) * kProfilePercentile)));
        std::array<float, kBands> percentileDb {};

        for (int band = 0; band < kBands; ++band)
        {
            unsigned int cumulative = 0;
            int chosen = kProfileBins - 1;
            for (int bin = 0; bin < kProfileBins; ++bin)
            {
                cumulative += routeProfileHistogram[routeIndex][static_cast<size_t> (band)][static_cast<size_t> (bin)];
                if (cumulative >= target)
                {
                    chosen = bin;
                    break;
                }
            }
            const float binT = (static_cast<float> (chosen) + 0.5f) / static_cast<float> (kProfileBins);
            percentileDb[static_cast<size_t> (band)] =
                kProfileMinDb + binT * (kProfileMaxDb - kProfileMinDb);
        }

        // Original browser 1-2-1 smoothing across the log-band grid.
        std::array<float, kBands> smoothDb {};
        for (int band = 0; band < kBands; ++band)
        {
            const float a = percentileDb[static_cast<size_t> (std::max (0, band - 1))];
            const float b = percentileDb[static_cast<size_t> (band)];
            const float c = percentileDb[static_cast<size_t> (std::min (kBands - 1, band + 1))];
            smoothDb[static_cast<size_t> (band)] = (a + 2.0f * b + c) * 0.25f;
            routeProfileDb[routeIndex][static_cast<size_t> (band)].store (
                smoothDb[static_cast<size_t> (band)], std::memory_order_relaxed);
            // Stable normalized copy retained for the temporal-FX similarity code.
            routeSpectrum[routeIndex][static_cast<size_t> (band)].store (
                clamp01 ((smoothDb[static_cast<size_t> (band)] - kProfileMinDb) /
                         (kProfileMaxDb - kProfileMinDb)), std::memory_order_relaxed);
        }

        routeProfileReady[routeIndex].store (
            routeProfileFrames[routeIndex] >= static_cast<unsigned int> (kProfileMinFrames),
            std::memory_order_relaxed);

        // Web depth metric: half-strength K weighting plus a gentle duty term.
        double weightedPower = 0.0;
        for (int band = 0; band < kBands; ++band)
        {
            const double f = std::max (28.0, static_cast<double> (
                bandHz[static_cast<size_t> (band)].load (std::memory_order_relaxed))));
            const double shelf = 4.0 / (1.0 + std::pow (1681.0 / f, 2.0));
            const double hp = 40.0 * std::log10 (f / std::sqrt (f * f + 38.0 * 38.0));
            const double k = (shelf + hp) * 0.55;
            weightedPower += std::pow (10.0, (static_cast<double> (smoothDb[static_cast<size_t> (band)]) + k) / 10.0);
        }
        const float duty = std::clamp (routeDuty[routeIndex].load (std::memory_order_relaxed), 0.02f, 1.0f);
        const float loudDb = static_cast<float> (
            10.0 * std::log10 (std::max (weightedPower, 1.0e-12)) + 4.0 * std::log10 (static_cast<double> (duty)));
        routeLoudnessDb[routeIndex].store (loudDb, std::memory_order_relaxed);
    }

'''
replace_between(
    "    void analyseSpectrum (size_t routeIndex, PWAV32FS buffer, int length)\n    {",
    "    void refreshMetadata ()",
    profile_analysis,
    "82nd-percentile streaming profile",
)

# Session reference is recomputed from learned dB profiles, so the original browser
# REF = loudest band + 15 dB mapping remains valid and can also move downward after a relearn.
profile_helpers = r'''    void refreshSessionProfileReference ()
    {
        float maxDb = -120.0f;
        for (int route = 0; route < kMaxRoutes; ++route)
        {
            if (!routeProfileReady[static_cast<size_t> (route)].load (std::memory_order_relaxed))
                continue;
            for (int band = 0; band < kBands; ++band)
                maxDb = std::max (maxDb, routeProfileDb[static_cast<size_t> (route)][static_cast<size_t> (band)].load (std::memory_order_relaxed));
        }
        sessionProfilePeakDb.store (maxDb, std::memory_order_relaxed);
    }

    float learnedShapeEnergy (size_t routeIndex, int band) const
    {
        if (routeIndex >= kMaxRoutes || band < 0 || band >= kBands)
            return 0.0f;
        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))
            return 0.0f;
        const float spectrumDb = routeProfileDb[routeIndex][static_cast<size_t> (band)].load (std::memory_order_relaxed);
        const float ref = sessionProfilePeakDb.load (std::memory_order_relaxed) + 15.0f;
        return clamp01 ((spectrumDb - (ref - kShapeDynDb)) / kShapeDynDb);
    }

'''
replace_once(
    "    struct ProjectedPoint\n    {",
    profile_helpers + "    struct ProjectedPoint\n    {",
    "profile shape helpers",
)

# All room geometry now reads the learned profile, not the current analyser block.
text = text.replace(
    "const float energy = routeSpectrum[routeIndex][static_cast<size_t> (band)].load (std::memory_order_relaxed);",
    "const float energy = learnedShapeEnergy (routeIndex, band);"
)

# Gate faint tails like the browser body grammar. This does not yet split lobes into
# separate meshes; it removes the live-spectrum ribbon behaviour and keeps only occupied bands.
text = text.replace(
    "const float halfWidth = 0.012f + energy * (0.055f + track.width * 0.090f) + expansionWorld;",
    "const float shaped = energy > kShapeGate ? std::pow (energy, 0.55f) : 0.0f;\n"
    "            const float halfWidth = shaped > 0.0f ?\n"
    "                (0.006f + shaped * (0.055f + track.width * 0.090f) + expansionWorld) : 0.0f;"
)

# Do not draw an unlearned half-random body while the histogram has only a few frames.
replace_once(
    "        const size_t routeIndex = static_cast<size_t> (route - 1);\n\n        const float halfDepth",
    "        const size_t routeIndex = static_cast<size_t> (route - 1);\n"
    "        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))\n"
    "            return;\n\n"
    "        const float halfDepth",
    "body waits for learned profile",
)

# Identity trace also waits until the profile is ready.
replace_once(
    "        if (!track.meta)\n            return;\n        const float halfDepth = std::clamp (track.volumeThickness * 0.5f, 0.018f, 0.10f);",
    "        if (!track.meta)\n"
    "            return;\n"
    "        const int traceRoute = track.meta->routeIndex;\n"
    "        if (traceRoute < 1 || traceRoute > kMaxRoutes ||\n"
    "            !routeProfileReady[static_cast<size_t> (traceRoute - 1)].load (std::memory_order_relaxed))\n"
    "            return;\n"
    "        const float halfDepth = std::clamp (track.volumeThickness * 0.5f, 0.018f, 0.10f);",
    "trace waits for learned profile",
)

# Refresh the cross-track reference before drawing this frame.
replace_once(
    "        SelectObject (dc, smallFont);\n        drawFieldGrid (dc, fieldArea);",
    "        SelectObject (dc, smallFont);\n"
    "        refreshSessionProfileReference ();\n"
    "        drawFieldGrid (dc, fieldArea);",
    "session profile reference refresh",
)

# -----------------------------------------------------------------------------
# Replace FX-topology Z with the browser's long-term loudness + duty depth. Reverb
# remains a separate attached aura and has zero effect on the source's Z position.
web_depth = r'''        // Browser depth model: long-term loudness + duty, never instantaneous peak,
        // width, current note, or reverb send. Loud sources sit forward; quiet sources sit back.
        float loudMin = 1.0e9f;
        float loudMax = -1.0e9f;
        for (const auto& track : active)
        {
            if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
                continue;
            const size_t idx = static_cast<size_t> (track.meta->routeIndex - 1);
            if (!routeProfileReady[idx].load (std::memory_order_relaxed))
                continue;
            const float l = routeLoudnessDb[idx].load (std::memory_order_relaxed);
            loudMin = std::min (loudMin, l);
            loudMax = std::max (loudMax, l);
        }
        if (loudMin > loudMax)
        {
            loudMin = -40.0f;
            loudMax = -26.0f;
        }
        const float measuredRange = std::max (0.0f, loudMax - loudMin);
        const float paddedSpan = std::clamp (measuredRange, 14.0f, 42.0f);
        const float loudLo = loudMin - paddedSpan * 0.12f;
        const float loudSpan = std::max (1.0f, measuredRange + paddedSpan * 0.24f);

        for (auto& track : active)
        {
            if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)
                continue;
            const size_t idx = static_cast<size_t> (track.meta->routeIndex - 1);
            if (!routeProfileReady[idx].load (std::memory_order_relaxed))
            {
                track.visualZ = 0.50f;
                track.volumeThickness = 0.060f;
                continue;
            }

            const float loudDb = routeLoudnessDb[idx].load (std::memory_order_relaxed);
            const float levelNorm = clamp01 ((loudDb - loudLo) / loudSpan);
            const float targetDepth = std::clamp (0.82f - levelNorm * 0.64f, 0.16f, 0.84f);
            float& smoothDepth = spatialDepth[idx];
            if (smoothDepth <= 0.001f)
                smoothDepth = targetDepth;
            else
                smoothDepth += (targetDepth - smoothDepth) * 0.020f;
            track.visualZ = smoothDepth;
            track.volumeThickness = 0.050f + levelNorm * 0.040f;
        }

'''
replace_between(
    "        // Stable apparent depth: musical level and width NEVER drive Z.\n",
    "        std::vector<DrawTrack> renderOrder = active;",
    web_depth,
    "web loudness depth model",
)

# -----------------------------------------------------------------------------
# UI language: make it explicit that geometry is learned and activity is only presence.
text = text.replace(
    "Stable pose holds through silence. Invert drag X/Y changes mouse orbit direction only; room axes never flip.",
    "Web-style learned bodies: geometry is an 82nd-percentile long-term profile; live audio only changes presence."
)
text = text.replace(
    "X PAN   |   Y FREQUENCY   |   Z LATCHED DEPTH",
    "X PAN   |   Y FREQUENCY   |   Z LONG-TERM LOUDNESS"
)
text = text.replace("PRIMARY TRACKS", "LEARNED TRACKS")

out.write_text(text, encoding="utf-8")
print(out)
