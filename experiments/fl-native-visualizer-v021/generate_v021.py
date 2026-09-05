from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v020 = root / "fl-native-visualizer-v020"

# Start from compile-green V0.20. V0.21 fixes the X-axis spatial grammar:
# the browser prototype used a stable body-width baseline plus onset-position
# voices, while the native build had collapsed everything into one M/S width.
runpy.run_path(str(v020 / "generate_v020.py"), run_name="__main__")
src = v020 / "generated" / "fieldv020.cpp"
out = here / "generated" / "fieldv021.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.21 could not find patch point: {label}")
    text = text.replace(old, new, 1)


# Identity / diagnostics filename.
text = text.replace("Field V0.20", "Field V0.21")
text = text.replace("FieldV020", "FieldV021")
text = text.replace("V020", "V021")
text = text.replace("v020", "v021")
text = text.replace("FieldV020_diagnostics.csv", "FieldV021_diagnostics.csv")
text = text.replace("LONG-WINDOW SPECTRUM", "WEB SPATIAL VOICES")

# DrawTrack carries transient render-only voice identity. The route remains one
# FL mixer source and the sidebar still has one row per routed track.
replace_once(
    "    float width = 0.0f;\n",
    "    float width = 0.0f;\n"
    "    int spatialVoiceIndex = 0;\n"
    "    int spatialVoiceCount = 1;\n",
    "DrawTrack spatial voice fields",
)

# Rolling onset-position model. This is the streaming equivalent of the browser
# analyseVoices() step: >=4 events, pan SD >= .07, then k=3/k=2 accepted only
# when adjacent centres are >= .16 and every cluster owns >=12% of weight.
replace_once(
    "    std::array<std::atomic<float>, kMaxRoutes> routeWidth;\n",
    "    std::array<std::atomic<float>, kMaxRoutes> routeWidth;\n"
    "    static constexpr int kSpatialEventHistory = 48;\n"
    "    static constexpr int kSpatialVoiceMax = 3;\n"
    "    std::array<std::array<float, kSpatialEventHistory>, kMaxRoutes> spatialEventPan {};\n"
    "    std::array<std::array<float, kSpatialEventHistory>, kMaxRoutes> spatialEventWeight {};\n"
    "    std::array<int, kMaxRoutes> spatialEventCount {};\n"
    "    std::array<int, kMaxRoutes> spatialEventWrite {};\n"
    "    std::array<float, kMaxRoutes> spatialPrevEnv {};\n"
    "    std::array<float, kMaxRoutes> spatialPrevPrevEnv {};\n"
    "    std::array<float, kMaxRoutes> spatialEnvelopePeak {};\n"
    "    std::array<unsigned long long, kMaxRoutes> spatialLastOnsetMs {};\n"
    "    std::array<std::atomic<int>, kMaxRoutes> spatialVoiceCount;\n"
    "    std::array<std::array<std::atomic<float>, kSpatialVoiceMax>, kMaxRoutes> spatialVoicePan;\n"
    "    std::array<std::array<std::atomic<float>, kSpatialVoiceMax>, kMaxRoutes> spatialVoiceWeight;\n",
    "spatial voice state",
)

# Initialise UI-readable voice state. Default is the browser's single centred voice.
replace_once(
    "        for (auto& p : routeWidth)\n            p.store (0.0f, std::memory_order_relaxed);",
    "        for (auto& p : routeWidth)\n"
    "            p.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& n : spatialVoiceCount) n.store (1, std::memory_order_relaxed);\n"
    "        for (auto& route : spatialVoicePan)\n"
    "            for (auto& p : route) p.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& route : spatialVoiceWeight)\n"
    "            for (auto& w : route) w.store (0.0f, std::memory_order_relaxed);",
    "spatial voice initialization",
)

# Onset spatial analysis is cheap and block-fast. It does not alter audio and does
# not wait for the long-term FFT/profile path.
replace_once(
    "            const float targetPeakDb = linearToDb (routePeak);\n",
    "            const float targetPeakDb = linearToDb (routePeak);\n"
    "            updateSpatialVoices (routeArrayIndex, balance, static_cast<float> (fastRms));\n",
    "feed onset-position analyser",
)

spatial_helpers = r'''    void recomputeSpatialVoices (size_t routeIndex)
    {
        if (routeIndex >= kMaxRoutes)
            return;
        const int n = std::clamp (spatialEventCount[routeIndex], 0, kSpatialEventHistory);
        auto publishSingle = [&] (float pan)
        {
            spatialVoicePan[routeIndex][0].store (std::clamp (pan, -1.0f, 1.0f), std::memory_order_relaxed);
            spatialVoiceWeight[routeIndex][0].store (1.0f, std::memory_order_relaxed);
            for (int j = 1; j < kSpatialVoiceMax; ++j)
            {
                spatialVoicePan[routeIndex][static_cast<size_t> (j)].store (0.0f, std::memory_order_relaxed);
                spatialVoiceWeight[routeIndex][static_cast<size_t> (j)].store (0.0f, std::memory_order_relaxed);
            }
            spatialVoiceCount[routeIndex].store (1, std::memory_order_release);
        };

        if (n < 4)
        {
            publishSingle (routeBalance[routeIndex].load (std::memory_order_relaxed));
            return;
        }

        std::array<float, kSpatialEventHistory> pans {};
        std::array<float, kSpatialEventHistory> weights {};
        float totalW = 0.0f;
        float mean = 0.0f;
        const int write = spatialEventWrite[routeIndex];
        const int start = n == kSpatialEventHistory ? write : 0;
        for (int i = 0; i < n; ++i)
        {
            const int src = (start + i) % kSpatialEventHistory;
            pans[static_cast<size_t> (i)] = spatialEventPan[routeIndex][static_cast<size_t> (src)];
            weights[static_cast<size_t> (i)] = std::max (1.0e-5f,
                spatialEventWeight[routeIndex][static_cast<size_t> (src)]);
            totalW += weights[static_cast<size_t> (i)];
            mean += pans[static_cast<size_t> (i)] * weights[static_cast<size_t> (i)];
        }
        mean /= std::max (1.0e-5f, totalW);
        float variance = 0.0f;
        for (int i = 0; i < n; ++i)
        {
            const float d = pans[static_cast<size_t> (i)] - mean;
            variance += d * d * weights[static_cast<size_t> (i)];
        }
        const float sd = std::sqrt (variance / std::max (1.0e-5f, totalW));
        if (sd < 0.07f)
        {
            publishSingle (mean);
            return;
        }

        for (int kTry : {3, 2})
        {
            if (n < kTry * 2)
                continue;
            float lo = pans[0], hi = pans[0];
            for (int i = 1; i < n; ++i)
            {
                lo = std::min (lo, pans[static_cast<size_t> (i)]);
                hi = std::max (hi, pans[static_cast<size_t> (i)]);
            }
            std::array<float, kSpatialVoiceMax> centres {};
            for (int j = 0; j < kTry; ++j)
                centres[static_cast<size_t> (j)] = lo + (hi - lo) *
                    (kTry == 1 ? 0.5f : static_cast<float> (j) / static_cast<float> (kTry - 1));
            std::array<int, kSpatialEventHistory> assign {};

            for (int iter = 0; iter < 20; ++iter)
            {
                std::array<float, kSpatialVoiceMax> sums {};
                std::array<float, kSpatialVoiceMax> sumW {};
                for (int i = 0; i < n; ++i)
                {
                    int best = 0;
                    float bestD = std::abs (pans[static_cast<size_t> (i)] - centres[0]);
                    for (int j = 1; j < kTry; ++j)
                    {
                        const float d = std::abs (pans[static_cast<size_t> (i)] - centres[static_cast<size_t> (j)]);
                        if (d < bestD) { bestD = d; best = j; }
                    }
                    assign[static_cast<size_t> (i)] = best;
                    sums[static_cast<size_t> (best)] += pans[static_cast<size_t> (i)] * weights[static_cast<size_t> (i)];
                    sumW[static_cast<size_t> (best)] += weights[static_cast<size_t> (i)];
                }
                for (int j = 0; j < kTry; ++j)
                    if (sumW[static_cast<size_t> (j)] > 1.0e-5f)
                        centres[static_cast<size_t> (j)] = sums[static_cast<size_t> (j)] / sumW[static_cast<size_t> (j)];
            }

            std::array<float, kSpatialVoiceMax> clusterW {};
            for (int i = 0; i < n; ++i)
                clusterW[static_cast<size_t> (assign[static_cast<size_t> (i)])] += weights[static_cast<size_t> (i)];

            // Sort centres with their weights, left -> right.
            for (int a = 0; a < kTry - 1; ++a)
                for (int b = a + 1; b < kTry; ++b)
                    if (centres[static_cast<size_t> (b)] < centres[static_cast<size_t> (a)])
                    {
                        std::swap (centres[static_cast<size_t> (a)], centres[static_cast<size_t> (b)]);
                        std::swap (clusterW[static_cast<size_t> (a)], clusterW[static_cast<size_t> (b)]);
                    }

            bool accepted = true;
            for (int j = 1; j < kTry; ++j)
                if (centres[static_cast<size_t> (j)] - centres[static_cast<size_t> (j - 1)] < 0.16f)
                    accepted = false;
            for (int j = 0; j < kTry; ++j)
                if (clusterW[static_cast<size_t> (j)] / std::max (1.0e-5f, totalW) < 0.12f)
                    accepted = false;
            if (!accepted)
                continue;

            for (int j = 0; j < kTry; ++j)
            {
                spatialVoicePan[routeIndex][static_cast<size_t> (j)].store (
                    std::clamp (centres[static_cast<size_t> (j)], -1.0f, 1.0f), std::memory_order_relaxed);
                spatialVoiceWeight[routeIndex][static_cast<size_t> (j)].store (
                    clusterW[static_cast<size_t> (j)] / std::max (1.0e-5f, totalW), std::memory_order_relaxed);
            }
            for (int j = kTry; j < kSpatialVoiceMax; ++j)
                spatialVoiceWeight[routeIndex][static_cast<size_t> (j)].store (0.0f, std::memory_order_relaxed);
            spatialVoiceCount[routeIndex].store (kTry, std::memory_order_release);
            return;
        }

        publishSingle (mean);
    }

    void updateSpatialVoices (size_t routeIndex, float blockPan, float fastRms)
    {
        if (routeIndex >= kMaxRoutes)
            return;
        float& peak = spatialEnvelopePeak[routeIndex];
        peak = std::max (fastRms, peak * 0.9995f);
        const float env = peak > 1.0e-7f ? clamp01 (fastRms / peak) : 0.0f;
        const float prev = spatialPrevEnv[routeIndex];
        const float prevPrev = spatialPrevPrevEnv[routeIndex];
        const unsigned long long now = GetTickCount64 ();
        const bool onset = env > 0.15f && env > prev * 1.25f &&
            prev >= prevPrev * 0.90f && now - spatialLastOnsetMs[routeIndex] >= 60ull;

        spatialPrevPrevEnv[routeIndex] = prev;
        spatialPrevEnv[routeIndex] = env;
        if (!onset)
            return;
        spatialLastOnsetMs[routeIndex] = now;

        const int write = spatialEventWrite[routeIndex];
        spatialEventPan[routeIndex][static_cast<size_t> (write)] = std::clamp (blockPan, -1.0f, 1.0f);
        spatialEventWeight[routeIndex][static_cast<size_t> (write)] = std::max (1.0e-5f, fastRms);
        spatialEventWrite[routeIndex] = (write + 1) % kSpatialEventHistory;
        spatialEventCount[routeIndex] = std::min (kSpatialEventHistory, spatialEventCount[routeIndex] + 1);
        recomputeSpatialVoices (routeIndex);
    }

'''
replace_once(
    "    void refreshMetadata ()\n",
    spatial_helpers + "    void refreshMetadata ()\n",
    "spatial voice helper functions",
)

# Expand a routed source into browser-style spatial voices for rendering only.
# This happens after route classification/list construction so the sidebar remains stable.
spatial_expand = r'''        std::vector<DrawTrack> spatialActive;
        spatialActive.reserve (active.size () * 2u);
        for (const auto& sourceTrack : active)
        {
            if (!sourceTrack.meta || sourceTrack.meta->routeIndex < 1 || sourceTrack.meta->routeIndex > kMaxRoutes)
                continue;
            const size_t idx = static_cast<size_t> (sourceTrack.meta->routeIndex - 1);
            const int voices = std::clamp (spatialVoiceCount[idx].load (std::memory_order_acquire), 1, kSpatialVoiceMax);
            if (voices <= 1)
            {
                DrawTrack d = sourceTrack;
                d.spatialVoiceIndex = 0;
                d.spatialVoiceCount = 1;
                // Browser Track.width defaults to 1. Do not squeeze geometry from M/S.
                d.width = 1.0f;
                const float learnedPan = spatialVoicePan[idx][0].load (std::memory_order_relaxed);
                if (spatialEventCount[idx] >= 4)
                    d.balance = learnedPan;
                spatialActive.push_back (d);
                continue;
            }
            for (int voice = 0; voice < voices; ++voice)
            {
                DrawTrack d = sourceTrack;
                d.spatialVoiceIndex = voice;
                d.spatialVoiceCount = voices;
                d.balance = spatialVoicePan[idx][static_cast<size_t> (voice)].load (std::memory_order_relaxed);
                d.width = 1.0f;
                spatialActive.push_back (d);
            }
        }
        active = std::move (spatialActive);

'''
replace_once(
    "        // Absolute per-source depth calibration. No cross-track normalization:\n",
    spatial_expand + "        // Absolute per-source depth calibration. No cross-track normalization:\n",
    "expand primary routes into spatial voices",
)

# Exact browser body-width baseline. Single voice at width=1 => ~0.207 pan units;
# multiple voices use compact ~0.156 bodies and separation comes from their centres.
replace_once(
    "            return (0.006f + shaped * (0.055f + track.width * 0.090f)) * swell;",
    "            const float browserBaseHalf = 0.30f *\n"
    "                (track.spatialVoiceCount > 1 ? 0.52f : (0.26f + 0.86f * 0.5f));\n"
    "            return browserBaseHalf * shaped * swell;",
    "browser body half-pan mapping",
)

# Frequency-cropped reverb/delay shells should use the same spatial width grammar.
text = text.replace(
    "            const float rx = (0.006f + shaped * (0.055f + track.width * 0.090f)) * swell;",
    "            const float browserBaseHalf = 0.30f *\n"
    "                (track.spatialVoiceCount > 1 ? 0.52f : (0.26f + 0.86f * 0.5f));\n"
    "            const float rx = browserBaseHalf * shaped * swell;"
)

# One readable route label, not one duplicate label per spatial voice.
replace_once(
    "        if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)\n            return;\n        const size_t routeIndex = static_cast<size_t> (track.meta->routeIndex - 1);",
    "        if (!track.meta || track.meta->routeIndex < 1 || track.meta->routeIndex > kMaxRoutes)\n"
    "            return;\n"
    "        if (track.spatialVoiceIndex != 0)\n"
    "            return;\n"
    "        const size_t routeIndex = static_cast<size_t> (track.meta->routeIndex - 1);",
    "single body label across spatial voices",
)

# Never let an unnamed classifier guess hide a primary instrument. Explicitly named
# AUX/REV/DLY/FX returns retain the return-attachment path.
old_unnamed = (
    "        return confidence >= 0.985f && bestLink >= 0.82f;"
)
if old_unnamed in text:
    text = text.replace(old_unnamed,
        "        return false; // unnamed routes remain primary; avoid multi-hit suppression",
        1)

text = text.replace(
    "Measured fixes: block-safe presence decay, conservative FX suppression, tighter occupied-frequency lobes.",
    "Web spatial model: stable browser body width plus onset-derived L/C/R voices; M/S no longer squeezes X spread."
)

out.write_text(text, encoding="utf-8")
print(out)
