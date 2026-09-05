from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v019 = root / "fl-native-visualizer-v019"

# Start from the measured-response V0.19 build.
runpy.run_path(str(v019 / "generate_v019.py"), run_name="__main__")
src = v019 / "generated" / "fieldv019.cpp"
out = here / "generated" / "fieldv020.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.20 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_function(signature: str, replacement: str, label: str) -> None:
    global text
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"V0.20 could not find function: {label}")
    brace = text.find('{', start)
    if brace < 0:
        raise RuntimeError(f"V0.20 could not find opening brace: {label}")
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
        raise RuntimeError(f"V0.20 could not find closing brace: {label}")
    text = text[:start] + replacement + text[end:]


# Fresh identity / diagnostics file.
text = text.replace("Field V0.19", "Field V0.20")
text = text.replace("FieldV019", "FieldV020")
text = text.replace("V019", "V020")
text = text.replace("v019", "v020")
text = text.replace("FieldV019_diagnostics.csv", "FieldV020_diagnostics.csv")
text = text.replace("MEASURED RESPONSE FIXES", "LONG-WINDOW SPECTRUM")

# -----------------------------------------------------------------------------
# Long analysis history. The old short-host-block Goertzel cannot resolve 28 Hz:
# at 44.1 kHz one 28 Hz cycle is ~1575 samples. A 4096-sample window gives useful
# low-band resolution while the separate fast-presence path remains block-fast.
replace_once(
    "constexpr int kProfileMinFrames = 4;",
    "constexpr int kProfileMinFrames = 2;\nconstexpr int kSpectrumWindowSize = 4096;",
    "profile/window constants",
)

replace_once(
    "    std::array<std::array<std::array<unsigned int, kProfileBins>, kBands>, kMaxRoutes> routeProfileHistogram {};\n",
    "    std::array<std::array<std::array<unsigned int, kProfileBins>, kBands>, kMaxRoutes> routeProfileHistogram {};\n"
    "    std::array<std::array<float, kSpectrumWindowSize>, kMaxRoutes> routeAnalysisWindow {};\n"
    "    std::array<int, kMaxRoutes> routeAnalysisWritePos {};\n"
    "    std::array<int, kMaxRoutes> routeAnalysisSampleCount {};\n",
    "long-window analysis state",
)

# Feed every filled audio block into the history, not only blocks already deemed
# loud. This preserves real silence between percussion hits and avoids artificial
# discontinuities from concatenating only active blocks.
replace_once(
    "            const float targetPeakDb = linearToDb (routePeak);",
    "            const float targetPeakDb = linearToDb (routePeak);\n"
    "            analyseSpectrumWindow (routeArrayIndex, routeBuffer, length, doSpectrum);",
    "continuous analysis-window feed",
)

old_call = (
    "                if (doSpectrum)\n"
    "                    analyseSpectrum (routeArrayIndex, routeBuffer, length);\n"
)
if old_call not in text:
    raise RuntimeError("V0.20 could not find inherited short-block spectrum call")
text = text.replace(old_call, "", 1)

spectrum_function = r'''    void analyseSpectrumWindow (size_t routeIndex, PWAV32FS buffer, int length, bool computeNow)
    {
        if (!buffer || length <= 0 || routeIndex >= kMaxRoutes)
            return;

        auto& history = routeAnalysisWindow[routeIndex];
        int& writePos = routeAnalysisWritePos[routeIndex];
        int& sampleCount = routeAnalysisSampleCount[routeIndex];

        for (int i = 0; i < length; ++i)
        {
            history[static_cast<size_t> (writePos)] = 0.5f * (buffer[i][0] + buffer[i][1]);
            writePos = (writePos + 1) & (kSpectrumWindowSize - 1);
            sampleCount = std::min (kSpectrumWindowSize, sampleCount + 1);
        }

        if (!computeNow || sampleCount < kSpectrumWindowSize)
            return;

        // Chronological 4096-sample frame, DC removed and Hann-windowed.
        std::array<float, kSpectrumWindowSize> real {};
        std::array<float, kSpectrumWindowSize> imag {};
        double mean = 0.0;
        for (int i = 0; i < kSpectrumWindowSize; ++i)
        {
            const int idx = (writePos + i) & (kSpectrumWindowSize - 1);
            mean += static_cast<double> (history[static_cast<size_t> (idx)]);
        }
        mean /= static_cast<double> (kSpectrumWindowSize);

        double windowSum = 0.0;
        for (int i = 0; i < kSpectrumWindowSize; ++i)
        {
            const int idx = (writePos + i) & (kSpectrumWindowSize - 1);
            const float w = 0.5f - 0.5f * std::cos (
                2.0f * kPi * static_cast<float> (i) / static_cast<float> (kSpectrumWindowSize - 1));
            real[static_cast<size_t> (i)] =
                (history[static_cast<size_t> (idx)] - static_cast<float> (mean)) * w;
            windowSum += static_cast<double> (w);
        }

        // In-place radix-2 FFT, split real/imag arrays to avoid library dependencies.
        for (int i = 1, j = 0; i < kSpectrumWindowSize; ++i)
        {
            int bit = kSpectrumWindowSize >> 1;
            for (; j & bit; bit >>= 1)
                j ^= bit;
            j ^= bit;
            if (i < j)
            {
                std::swap (real[static_cast<size_t> (i)], real[static_cast<size_t> (j)]);
                std::swap (imag[static_cast<size_t> (i)], imag[static_cast<size_t> (j)]);
            }
        }

        for (int len = 2; len <= kSpectrumWindowSize; len <<= 1)
        {
            const float angle = -2.0f * kPi / static_cast<float> (len);
            const float wLenR = std::cos (angle);
            const float wLenI = std::sin (angle);
            for (int base = 0; base < kSpectrumWindowSize; base += len)
            {
                float wr = 1.0f;
                float wi = 0.0f;
                const int half = len >> 1;
                for (int j = 0; j < half; ++j)
                {
                    const int a = base + j;
                    const int b = a + half;
                    const float br = real[static_cast<size_t> (b)] * wr - imag[static_cast<size_t> (b)] * wi;
                    const float bi = real[static_cast<size_t> (b)] * wi + imag[static_cast<size_t> (b)] * wr;
                    const float ar = real[static_cast<size_t> (a)];
                    const float ai = imag[static_cast<size_t> (a)];
                    real[static_cast<size_t> (a)] = ar + br;
                    imag[static_cast<size_t> (a)] = ai + bi;
                    real[static_cast<size_t> (b)] = ar - br;
                    imag[static_cast<size_t> (b)] = ai - bi;
                    const float nextWr = wr * wLenR - wi * wLenI;
                    wi = wr * wLenI + wi * wLenR;
                    wr = nextWr;
                }
            }
        }

        const float sr = std::max (8000.0f, sampleRate.load (std::memory_order_relaxed));
        const float binHz = sr / static_cast<float> (kSpectrumWindowSize);
        const float normalization = 2.0f / static_cast<float> (std::max (1.0, windowSum));
        std::array<float, kBands> percentileInputDb {};

        // Read each logarithmic band from the FFT bins between geometric band edges.
        // Max-within-band preserves narrow musical components while Hann + long window
        // sharply reduces the fake 28 Hz occupancy observed in V0.18/V0.19.
        for (int band = 0; band < kBands; ++band)
        {
            const float center = bandHz[static_cast<size_t> (band)].load (std::memory_order_relaxed);
            float lowEdge = center;
            float highEdge = center;
            if (band > 0)
            {
                const float prev = bandHz[static_cast<size_t> (band - 1)].load (std::memory_order_relaxed);
                lowEdge = std::sqrt (std::max (1.0f, prev * center));
            }
            else if (band + 1 < kBands)
            {
                const float next = bandHz[static_cast<size_t> (band + 1)].load (std::memory_order_relaxed);
                lowEdge = center / std::sqrt (std::max (1.0001f, next / center));
            }
            if (band + 1 < kBands)
            {
                const float next = bandHz[static_cast<size_t> (band + 1)].load (std::memory_order_relaxed);
                highEdge = std::sqrt (std::max (1.0f, center * next));
            }
            else if (band > 0)
            {
                const float prev = bandHz[static_cast<size_t> (band - 1)].load (std::memory_order_relaxed);
                highEdge = center * std::sqrt (std::max (1.0001f, center / prev));
            }

            int firstBin = std::max (1, static_cast<int> (std::floor (lowEdge / binHz)));
            int lastBin = std::min (kSpectrumWindowSize / 2 - 1,
                static_cast<int> (std::ceil (highEdge / binHz)));
            if (lastBin < firstBin)
                lastBin = firstBin;

            float maxAmplitude = 0.0f;
            for (int bin = firstBin; bin <= lastBin; ++bin)
            {
                const float re = real[static_cast<size_t> (bin)];
                const float im = imag[static_cast<size_t> (bin)];
                const float amplitude = std::sqrt (re * re + im * im) * normalization;
                maxAmplitude = std::max (maxAmplitude, amplitude);
            }
            percentileInputDb[static_cast<size_t> (band)] = std::clamp (
                linearToDb (maxAmplitude), kProfileMinDb, kProfileMaxDb);
        }

        // Feed the same long-term 82nd-percentile learner used by the web-style body.
        for (int band = 0; band < kBands; ++band)
        {
            const float db = percentileInputDb[static_cast<size_t> (band)];
            const float t = clamp01 ((db - kProfileMinDb) / (kProfileMaxDb - kProfileMinDb));
            const int bin = std::clamp (
                static_cast<int> (std::floor (t * static_cast<float> (kProfileBins))), 0, kProfileBins - 1);
            ++routeProfileHistogram[routeIndex][static_cast<size_t> (band)][static_cast<size_t> (bin)];
        }

        ++routeProfileFrames[routeIndex];
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

        std::array<float, kBands> smoothDb {};
        for (int band = 0; band < kBands; ++band)
        {
            const float a = percentileDb[static_cast<size_t> (std::max (0, band - 1))];
            const float b = percentileDb[static_cast<size_t> (band)];
            const float c = percentileDb[static_cast<size_t> (std::min (kBands - 1, band + 1))];
            smoothDb[static_cast<size_t> (band)] = (a + 2.0f * b + c) * 0.25f;
            routeProfileDb[routeIndex][static_cast<size_t> (band)].store (
                smoothDb[static_cast<size_t> (band)], std::memory_order_relaxed);
            routeSpectrum[routeIndex][static_cast<size_t> (band)].store (
                clamp01 ((smoothDb[static_cast<size_t> (band)] - kProfileMinDb) /
                         (kProfileMaxDb - kProfileMinDb)), std::memory_order_relaxed);
        }

        routeProfileReady[routeIndex].store (
            routeProfileFrames[routeIndex] >= static_cast<unsigned int> (kProfileMinFrames),
            std::memory_order_relaxed);

        float profilePeakDb = -120.0f;
        for (float db : smoothDb)
            profilePeakDb = std::max (profilePeakDb, db);
        const float duty = routeDuty[routeIndex].load (std::memory_order_relaxed);
        const float dutyPenalty = 10.0f * std::log10 (std::max (0.02f, duty));
        routeLoudnessDb[routeIndex].store (profilePeakDb + 0.55f * dutyPenalty, std::memory_order_relaxed);

        float oldSessionPeak = sessionProfilePeakDb.load (std::memory_order_relaxed);
        while (profilePeakDb > oldSessionPeak &&
               !sessionProfilePeakDb.compare_exchange_weak (
                   oldSessionPeak, profilePeakDb, std::memory_order_relaxed)) {}
    }
'''

replace_function(
    "    void analyseSpectrum (size_t routeIndex, PWAV32FS buffer, int length)",
    spectrum_function,
    "short-block spectrum analyzer",
)

text = text.replace(
    "Measured fixes: block-safe presence decay, conservative FX suppression, tighter occupied-frequency lobes.",
    "Long-window spectrum: 4096-sample Hann FFT geometry; fast presence remains independent."
)
text = text.replace(
    "V0.19 FIXED: RAW -> PRESENCE -> PROFILE -> Z -> DRAW",
    "V0.20: FAST PRESENCE + 4096-SAMPLE SPECTRAL GEOMETRY"
)

out.write_text(text, encoding="utf-8")
print(out)
