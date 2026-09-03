from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v005_dir = root / "fl-native-visualizer-v005"

# Generate the validated V0.05 source first, then layer V0.06 behavior on top.
runpy.run_path(str(v005_dir / "generate_v005.py"), run_name="__main__")
src = v005_dir / "generated" / "fieldv005.cpp"
out = here / "generated" / "fieldv006.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.06 generator could not find patch point: {label}")
    text = text.replace(old, new, 1)


# Fresh FL-native plugin identity.
text = text.replace("Field V0.05 Stable Visualizer", "Field V0.06 FX Aware Visualizer")
text = text.replace("FieldV005", "FieldV006")
text = text.replace("V0.05", "V0.06")
text = text.replace("V005", "V006")

replace_once(
    "#include <cmath>\n",
    "#include <cmath>\n#include <cctype>\n",
    "cctype include",
)

replace_once(
    "constexpr int kBands = 24;\n",
    "constexpr int kBands = 24;\n"
    "constexpr int kHistoryFrames = 160;\n"
    "constexpr std::array<int, 11> kFxLags {2, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128};\n",
    "FX constants",
)

replace_once(
    "struct DrawTrack\n{\n"
    "    const InputMetadata* meta = nullptr;\n"
    "    float peakDb = -120.0f;\n"
    "    float balance = 0.0f;\n"
    "    float width = 0.0f;\n"
    "};\n",
    "struct DrawTrack\n{\n"
    "    const InputMetadata* meta = nullptr;\n"
    "    float peakDb = -120.0f;\n"
    "    float balance = 0.0f;\n"
    "    float width = 0.0f;\n"
    "};\n\n"
    "struct FxLink\n{\n"
    "    int returnRoute = 0;\n"
    "    int sourceRoute = 0;\n"
    "    int lagFrames = 0;\n"
    "    float score = 0.0f;\n"
    "    float wetAmount = 0.0f;\n"
    "    bool delayLike = false;\n"
    "};\n",
    "FxLink struct",
)

replace_once(
    "        for (auto& route : routeSpectrum)\n"
    "            for (auto& band : route)\n"
    "                band.store (0.0f, std::memory_order_relaxed);\n\n"
    "        updateBandCoefficients (44100.0f);",
    "        for (auto& route : routeSpectrum)\n"
    "            for (auto& band : route)\n"
    "                band.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& flag : everActive)\n"
    "            flag.store (false, std::memory_order_relaxed);\n"
    "        for (auto& route : routeEnvelopeHistory)\n"
    "            for (auto& frame : route)\n"
    "                frame.store (0.0f, std::memory_order_relaxed);\n\n"
    "        updateBandCoefficients (44100.0f);",
    "history initialization",
)

replace_once(
    "        if (++idleCounter >= 6)\n"
    "        {\n"
    "            idleCounter = 0;\n"
    "            refreshMetadata ();\n"
    "        }\n\n"
    "        if (editorWindow)",
    "        if (++idleCounter >= 6)\n"
    "        {\n"
    "            idleCounter = 0;\n"
    "            refreshMetadata ();\n"
    "            if (++fxClassifyCounter >= 4)\n"
    "            {\n"
    "                fxClassifyCounter = 0;\n"
    "                classifyTemporalFx ();\n"
    "            }\n"
    "        }\n\n"
    "        if (editorWindow)",
    "idle classifier cadence",
)

replace_once(
    "        const int count = std::clamp (\n"
    "            reportedRouteCount.load (std::memory_order_relaxed), 0, kMaxRoutes);\n\n"
    "        for (int route = 0; route < count; ++route)",
    "        const int count = std::clamp (\n"
    "            reportedRouteCount.load (std::memory_order_relaxed), 0, kMaxRoutes);\n\n"
    "        std::array<float, kMaxRoutes> historyFrame {};\n\n"
    "        for (int route = 0; route < count; ++route)",
    "history frame allocation",
)

replace_once(
    "            const float targetPeakDb = linearToDb (routePeak);\n"
    "            auto& peakCell = routePeakDb[routeArrayIndex];",
    "            const float targetPeakDb = linearToDb (routePeak);\n"
    "            historyFrame[routeArrayIndex] = clamp01 ((targetPeakDb + 84.0f) / 60.0f);\n"
    "            if (targetPeakDb > -88.0f)\n"
    "                everActive[routeArrayIndex].store (true, std::memory_order_relaxed);\n\n"
    "            auto& peakCell = routePeakDb[routeArrayIndex];",
    "ever-active latch",
)

replace_once(
    "            ++live;\n"
    "        }\n\n"
    "        liveRouteCount.store (live, std::memory_order_relaxed);",
    "            ++live;\n"
    "        }\n\n"
    "        const int historySlot = historyWriteIndex.fetch_add (1, std::memory_order_relaxed) % kHistoryFrames;\n"
    "        for (int route = 0; route < count; ++route)\n"
    "            routeEnvelopeHistory[static_cast<size_t> (route)][static_cast<size_t> (historySlot)].store (\n"
    "                historyFrame[static_cast<size_t> (route)], std::memory_order_relaxed);\n\n"
    "        liveRouteCount.store (live, std::memory_order_relaxed);",
    "history commit",
)

classifier = r'''
    float historySample (size_t routeIndex, int chronologicalIndex, int available, int writes) const
    {
        if (routeIndex >= kMaxRoutes || available <= 0 || chronologicalIndex < 0 || chronologicalIndex >= available)
            return 0.0f;
        const int oldestAbsolute = writes - available;
        const int absolute = oldestAbsolute + chronologicalIndex;
        const int slot = ((absolute % kHistoryFrames) + kHistoryFrames) % kHistoryFrames;
        return routeEnvelopeHistory[routeIndex][static_cast<size_t> (slot)].load (std::memory_order_relaxed);
    }

    float envelopeCorrelation (size_t sourceIndex, size_t returnIndex, int lag, int available, int writes) const
    {
        const int n = available - lag;
        if (n < 24)
            return 0.0f;

        double sx = 0.0, sy = 0.0;
        for (int i = lag; i < available; ++i)
        {
            sx += historySample (sourceIndex, i - lag, available, writes);
            sy += historySample (returnIndex, i, available, writes);
        }
        const double mx = sx / n;
        const double my = sy / n;

        double cov = 0.0, vx = 0.0, vy = 0.0;
        for (int i = lag; i < available; ++i)
        {
            const double x = historySample (sourceIndex, i - lag, available, writes) - mx;
            const double y = historySample (returnIndex, i, available, writes) - my;
            cov += x * y;
            vx += x * x;
            vy += y * y;
        }
        const double denom = std::sqrt (vx * vy);
        if (denom < 1.0e-9)
            return 0.0f;
        return static_cast<float> (std::clamp (cov / denom, -1.0, 1.0));
    }

    float tailRatio (size_t sourceIndex, size_t returnIndex, int lag, int available, int writes) const
    {
        double tail = 0.0;
        double total = 0.0;
        for (int i = lag; i < available; ++i)
        {
            const float x = historySample (sourceIndex, i - lag, available, writes);
            const float y = historySample (returnIndex, i, available, writes);
            total += y;
            if (x < 0.10f && y > 0.035f)
                tail += y;
        }
        return total > 1.0e-6 ? static_cast<float> (std::clamp (tail / total, 0.0, 1.0)) : 0.0f;
    }

    float recentMean (size_t routeIndex, int available, int writes) const
    {
        if (available <= 0)
            return 0.0f;
        const int start = std::max (0, available - 48);
        double sum = 0.0;
        for (int i = start; i < available; ++i)
            sum += historySample (routeIndex, i, available, writes);
        return static_cast<float> (sum / std::max (1, available - start));
    }

    int temporalNameHint (int route) const
    {
        const InputMetadata* meta = nullptr;
        for (const auto& item : inputs)
            if (item.routeIndex == route) { meta = &item; break; }
        if (!meta)
            return 0;

        std::string s = !meta->visibleName.empty () ? meta->visibleName : meta->userName;
        for (char& c : s)
            c = static_cast<char> (std::tolower (static_cast<unsigned char> (c)));

        const auto has = [&s] (const char* needle) { return s.find (needle) != std::string::npos; };
        if (has ("delay") || has ("echo") || has ("slap"))
            return 2;
        if (has ("reverb") || has ("verb") || has ("room") || has ("hall") || has ("plate"))
            return 1;
        if (has ("return") || has ("send") || has ("wet") || has ("fx"))
            return 3;
        return 0;
    }

    void classifyTemporalFx ()
    {
        fxLinks.clear ();

        const int writes = historyWriteIndex.load (std::memory_order_relaxed);
        const int available = std::min (writes, kHistoryFrames);
        if (available < 48)
            return;

        const int count = std::clamp (reportedRouteCount.load (std::memory_order_relaxed), 0, kMaxRoutes);

        struct Candidate
        {
            int sourceRoute = 0;
            int lag = 0;
            float score = 0.0f;
            float delayedCorr = 0.0f;
            float zeroCorr = 0.0f;
            float tail = 0.0f;
        };

        for (int returnRoute = 1; returnRoute <= count; ++returnRoute)
        {
            const size_t r = static_cast<size_t> (returnRoute - 1);
            if (!everActive[r].load (std::memory_order_relaxed))
                continue;

            std::vector<Candidate> candidates;
            const int nameHint = temporalNameHint (returnRoute);
            const float returnWidthNow = routeWidth[r].load (std::memory_order_relaxed);

            for (int sourceRoute = 1; sourceRoute <= count; ++sourceRoute)
            {
                if (sourceRoute == returnRoute)
                    continue;
                const size_t s = static_cast<size_t> (sourceRoute - 1);
                if (!everActive[s].load (std::memory_order_relaxed))
                    continue;

                const float zero = envelopeCorrelation (s, r, 0, available, writes);
                float best = -1.0f;
                int bestLag = 0;
                for (int lag : kFxLags)
                {
                    if (lag >= available - 24)
                        continue;
                    const float c = envelopeCorrelation (s, r, lag, available, writes);
                    if (c > best)
                    {
                        best = c;
                        bestLag = lag;
                    }
                }

                if (bestLag <= 0 || best < 0.30f)
                    continue;

                const float tail = tailRatio (s, r, bestLag, available, writes);
                const float lagAdvantage = best - zero;
                const float widthDelta = std::max (0.0f,
                    returnWidthNow - routeWidth[s].load (std::memory_order_relaxed));
                const float hintBoost = nameHint == 0 ? 0.0f : (nameHint == 3 ? 0.035f : 0.075f);

                const float score =
                    best * 0.56f +
                    tail * 0.22f +
                    clamp01 ((lagAdvantage + 0.05f) * 2.2f) * 0.13f +
                    clamp01 (widthDelta * 2.5f) * 0.09f +
                    hintBoost;

                const bool temporal = best > 0.40f &&
                    (lagAdvantage > 0.035f || tail > 0.22f || (nameHint != 0 && tail > 0.12f));
                if (!temporal || score < 0.46f)
                    continue;

                candidates.push_back ({sourceRoute, bestLag, score, best, zero, tail});
            }

            if (candidates.empty ())
                continue;

            std::sort (candidates.begin (), candidates.end (), [] (const Candidate& a, const Candidate& b)
            {
                return a.score > b.score;
            });

            const float top = candidates.front ().score;
            if (top < 0.50f)
                continue;

            float acceptedScoreSum = 0.0f;
            int accepted = 0;
            for (const auto& c : candidates)
            {
                if (accepted >= 4 || c.score < std::max (0.46f, top * 0.72f))
                    break;
                acceptedScoreSum += c.score;
                ++accepted;
            }
            if (accepted == 0 || acceptedScoreSum <= 0.0f)
                continue;

            const float returnEnergy = clamp01 (recentMean (r, available, writes) * 1.8f);
            for (int i = 0; i < accepted; ++i)
            {
                const auto& c = candidates[static_cast<size_t> (i)];
                bool delayLike = (c.delayedCorr > 0.62f && (c.delayedCorr - c.zeroCorr) > 0.09f && c.tail < 0.62f);
                if (nameHint == 2) delayLike = true;
                if (nameHint == 1) delayLike = false;

                FxLink link;
                link.returnRoute = returnRoute;
                link.sourceRoute = c.sourceRoute;
                link.lagFrames = c.lag;
                link.score = c.score;
                link.wetAmount = clamp01 (returnEnergy * (c.score / acceptedScoreSum) * 2.2f);
                link.delayLike = delayLike;
                fxLinks.push_back (link);
            }
        }
    }

    bool isFxReturnRoute (int route) const
    {
        for (const auto& link : fxLinks)
            if (link.returnRoute == route)
                return true;
        return false;
    }

    void fxAmountsForSource (int sourceRoute, float& reverb, float& delay) const
    {
        reverb = 0.0f;
        delay = 0.0f;
        for (const auto& link : fxLinks)
        {
            if (link.sourceRoute != sourceRoute)
                continue;
            if (link.delayLike)
                delay = clamp01 (delay + link.wetAmount * link.score);
            else
                reverb = clamp01 (reverb + link.wetAmount * link.score);
        }
    }

'''

replace_once(
    "    void refreshMetadata ()\n    {",
    classifier + "    void refreshMetadata ()\n    {",
    "FX classifier methods",
)

aura = r'''
    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)
    {
        if (!track.meta || (reverbAmount <= 0.01f && delayAmount <= 0.01f))
            return;

        const int route = track.meta->routeIndex;
        if (route < 1 || route > kMaxRoutes)
            return;
        const size_t routeIndex = static_cast<size_t> (route - 1);
        const int centerBase = (area.left + area.right) / 2;
        const float halfSpan = static_cast<float> (area.right - area.left) * 0.40f;
        const int centerX = centerBase + static_cast<int> (track.balance * halfSpan);

        COLORREF raw = static_cast<COLORREF> (track.meta->color & 0x00FFFFFF);
        if (raw == RGB (0, 0, 0))
            raw = RGB (115, 160, 190);
        const COLORREF bg = RGB (16, 20, 26);

        auto drawLayer = [&] (float expansion, int xOffset, float fade, bool fillIt)
        {
            std::array<POINT, kBands * 2> points {};
            for (int band = 0; band < kBands; ++band)
            {
                const float energy = routeSpectrum[routeIndex][static_cast<size_t> (band)].load (std::memory_order_relaxed);
                const float hz = bandHz[static_cast<size_t> (band)].load (std::memory_order_relaxed);
                const int y = yForFrequency (hz, area.top, area.bottom);
                const float halfWidth = 6.0f + energy * (24.0f + track.width * 42.0f) + expansion;
                points[static_cast<size_t> (band)] = {centerX + xOffset - static_cast<int> (halfWidth), y};
                points[static_cast<size_t> (kBands * 2 - 1 - band)] = {centerX + xOffset + static_cast<int> (halfWidth), y};
            }

            const COLORREF c = mixColor (raw, bg, fade);
            HPEN pen = CreatePen (PS_SOLID, 1, c);
            HBRUSH brush = fillIt ? CreateSolidBrush (mixColor (raw, bg, std::min (0.96f, fade + 0.08f))) :
                                   static_cast<HBRUSH> (GetStockObject (NULL_BRUSH));
            auto oldPen = SelectObject (dc, pen);
            auto oldBrush = SelectObject (dc, brush);
            Polygon (dc, points.data (), static_cast<int> (points.size ()));
            SelectObject (dc, oldBrush);
            SelectObject (dc, oldPen);
            DeleteObject (pen);
            if (fillIt)
                DeleteObject (brush);
        };

        if (reverbAmount > 0.01f)
        {
            drawLayer (10.0f + reverbAmount * 34.0f, 0, 0.93f, true);
            drawLayer (6.0f + reverbAmount * 23.0f, 0, 0.86f, false);
            drawLayer (3.0f + reverbAmount * 13.0f, 0, 0.78f, false);
        }

        if (delayAmount > 0.01f)
        {
            const int spread = 9 + static_cast<int> (delayAmount * 18.0f);
            drawLayer (2.0f + delayAmount * 6.0f, -spread * 2, 0.95f, false);
            drawLayer (2.0f + delayAmount * 5.0f, spread * 2, 0.92f, false);
            drawLayer (1.0f + delayAmount * 3.0f, spread, 0.84f, false);
        }
    }

'''

replace_once(
    "    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)\n    {",
    aura + "    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)\n    {",
    "FX aura drawing",
)

# Temporal FX returns remain audible in reconstruction, but stop occupying their own primary visual body.
replace_once(
    "            if (peak <= -78.0f)\n"
    "                continue;\n"
    "            DrawTrack d;",
    "            if (peak <= -78.0f)\n"
    "                continue;\n"
    "            if (isFxReturnRoute (item.routeIndex))\n"
    "                continue;\n"
    "            DrawTrack d;",
    "skip standalone FX-return bodies",
)

replace_once(
    "        for (const auto& track : active)\n"
    "            drawSpectralBody (dc, track, fieldArea);",
    "        for (const auto& track : active)\n"
    "        {\n"
    "            float reverbAmount = 0.0f, delayAmount = 0.0f;\n"
    "            fxAmountsForSource (track.meta ? track.meta->routeIndex : 0, reverbAmount, delayAmount);\n"
    "            drawFxAura (dc, track, fieldArea, reverbAmount, delayAmount);\n"
    "            drawSpectralBody (dc, track, fieldArea);\n"
    "        }",
    "draw attached FX layers",
)

# Sidebar now contains every route that has produced meaningful audio at least once this plugin session.
replace_once(
    "        std::vector<DrawTrack> stableList = active;\n"
    "        std::sort (stableList.begin (), stableList.end (), [] (const DrawTrack& a, const DrawTrack& b)",
    "        std::vector<DrawTrack> stableList;\n"
    "        stableList.reserve (inputs.size ());\n"
    "        for (const auto& item : inputs)\n"
    "        {\n"
    "            if (item.routeIndex < 1 || item.routeIndex > kMaxRoutes)\n"
    "                continue;\n"
    "            const size_t idx = static_cast<size_t> (item.routeIndex - 1);\n"
    "            if (!everActive[idx].load (std::memory_order_relaxed))\n"
    "                continue;\n"
    "            DrawTrack d;\n"
    "            d.meta = &item;\n"
    "            d.peakDb = routePeakDb[idx].load (std::memory_order_relaxed);\n"
    "            d.balance = routeBalance[idx].load (std::memory_order_relaxed);\n"
    "            d.width = routeWidth[idx].load (std::memory_order_relaxed);\n"
    "            stableList.push_back (d);\n"
    "        }\n"
    "        std::sort (stableList.begin (), stableList.end (), [] (const DrawTrack& a, const DrawTrack& b)",
    "persistent sidebar list",
)

replace_once(
    "            if (display.empty ())\n"
    "                display = \"(unnamed)\";\n"
    "            const auto wide = ansiToWide (display);",
    "            if (display.empty ())\n"
    "                display = \"(unnamed)\";\n"
    "            if (isFxReturnRoute (item.routeIndex))\n"
    "                display += \"  [FX RETURN]\";\n"
    "            const auto wide = ansiToWide (display);",
    "FX return sidebar tag",
)

replace_once(
    "    int idleCounter = 0;\n"
    "    unsigned int analysisBlockCounter = 0;",
    "    int idleCounter = 0;\n"
    "    int fxClassifyCounter = 0;\n"
    "    unsigned int analysisBlockCounter = 0;",
    "classifier counter member",
)

replace_once(
    "    std::array<std::atomic<float>, kMaxRoutes> routePeakDb;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeBalance;",
    "    std::array<std::atomic<float>, kMaxRoutes> routePeakDb;\n"
    "    std::array<std::atomic<bool>, kMaxRoutes> everActive;\n"
    "    std::array<std::array<std::atomic<float>, kHistoryFrames>, kMaxRoutes> routeEnvelopeHistory;\n"
    "    std::atomic<int> historyWriteIndex {0};\n"
    "    std::vector<FxLink> fxLinks;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeBalance;",
    "persistent/FX state members",
)

replace_once(
    "Stable visual objects: mixer order is fixed; spectral shape, pan and width use perceptual smoothing.",
    "Persistent mixer-order list. Temporal FX returns are attached to their likely source objects as faded ambience/echo layers.",
    "V0.06 UI copy",
)

out.write_text(text, encoding="utf-8")
print(out)
