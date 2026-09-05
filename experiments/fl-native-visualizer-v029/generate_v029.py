from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v028 = root / "fl-native-visualizer-v028"

# Start from compile-green V0.28 readable-EQ build.
runpy.run_path(str(v028 / "generate_v028.py"), run_name="__main__")
src = v028 / "generated" / "fieldv028.cpp"
out = here / "generated" / "fieldv029.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.29 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.29 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.29 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


# Identity. Calibrated X/Z and 500 ms disappear remain inherited from V0.28.
text = text.replace("Field V0.28", "Field V0.29")
text = text.replace("FieldV028", "FieldV029")
text = text.replace("V028", "V029")
text = text.replace("v028", "v029")
text = text.replace("FieldV028_diagnostics.csv", "FieldV029_diagnostics.csv")
text = text.replace("READABLE EQ DELTA", "STABLE EQ DELTA")

# -----------------------------------------------------------------------------
# UI-thread EQ state. V0.28 compared every raw FFT frame straight to the long-term
# profile, so vocal formants/syllables looked like wildly moving EQ. V0.29 keeps a
# temporally smoothed, coherence-gated delta plus badge hysteresis.
replace_once(
    "    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeLiveSpectrumDb;\n",
    "    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeLiveSpectrumDb;\n"
    "    std::array<std::array<float, kBands>, kMaxRoutes> routeEqStableDb {};\n"
    "    std::array<unsigned long long, kMaxRoutes> routeEqStableLastMs {};\n"
    "    std::array<int, kMaxRoutes> routeEqCandidateCode {};\n"
    "    std::array<unsigned long long, kMaxRoutes> routeEqCandidateSinceMs {};\n"
    "    std::array<int, kMaxRoutes> routeEqBadgeCode {};\n"
    "    std::array<float, kMaxRoutes> routeEqBadgeDelta {};\n"
    "    std::array<unsigned long long, kMaxRoutes> routeEqBadgeHoldUntilMs {};\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeEqDiagHz;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeEqDiagDb;\n",
    "stable EQ state",
)

replace_once(
    "        for (auto& route : routeLiveSpectrumDb)\n"
    "            for (auto& band : route)\n"
    "                band.store (-120.0f, std::memory_order_relaxed);",
    "        for (auto& route : routeLiveSpectrumDb)\n"
    "            for (auto& band : route)\n"
    "                band.store (-120.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : routeEqDiagHz) v.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : routeEqDiagDb) v.store (0.0f, std::memory_order_relaxed);",
    "EQ diagnostic initialization",
)

# -----------------------------------------------------------------------------
# Replace V0.28's frame-reactive delta with a level-normalized, temporally smoothed,
# neighbour-coherent delta. Geometry now changes deliberately rather than tracking
# every vowel/formant. Badge selection is prepared here too so it can be hysteretic.
stable_delta = r'''        std::array<float, kBands> baseShape {};
        std::array<float, kBands> liveMinusLearned {};
        std::array<float, kBands> targetEqDeltaDb {};
        std::array<float, kBands> eqDeltaDb {};
        std::array<float, kBands> shape {};

        float broadbandNumerator = 0.0f;
        float broadbandDenominator = 0.0f;
        for (int i = 0; i < kBands; ++i)
        {
            baseShape[static_cast<size_t> (i)] = learnedShapeEnergy (routeIndex, i);
            const float learnedDb = routeProfileDb[routeIndex][static_cast<size_t> (i)].load (
                std::memory_order_relaxed);
            const float liveDb = routeLiveSpectrumDb[routeIndex][static_cast<size_t> (i)].load (
                std::memory_order_relaxed);
            const float difference = std::clamp (liveDb - learnedDb, -18.0f, 18.0f);
            liveMinusLearned[static_cast<size_t> (i)] = difference;

            // Remove ordinary whole-signal level movement before looking for EQ.
            // Weight only meaningful learned bands so silence/noise does not move the reference.
            if (learnedDb > -105.0f && liveDb > -118.0f && baseShape[static_cast<size_t> (i)] > 0.035f)
            {
                const float w = 0.18f + baseShape[static_cast<size_t> (i)];
                broadbandNumerator += difference * w;
                broadbandDenominator += w;
            }
        }
        const float broadbandOffset = broadbandDenominator > 0.001f
            ? broadbandNumerator / broadbandDenominator : 0.0f;

        // Frequency smoothing first. 2 dB dead-zone is intentionally more conservative
        // than V0.28's 1.25 dB because speech/music spectral content naturally moves.
        std::array<float, kBands> normalizedDelta {};
        for (int i = 0; i < kBands; ++i)
        {
            float d = std::clamp (liveMinusLearned[static_cast<size_t> (i)] - broadbandOffset,
                -10.0f, 10.0f);
            if (std::abs (d) < 2.0f) d = 0.0f;
            normalizedDelta[static_cast<size_t> (i)] = d;
        }
        for (int i = 0; i < kBands; ++i)
        {
            const float a = normalizedDelta[static_cast<size_t> (std::max (0, i - 1))];
            const float b = normalizedDelta[static_cast<size_t> (i)];
            const float c = normalizedDelta[static_cast<size_t> (std::min (kBands - 1, i + 1))];
            targetEqDeltaDb[static_cast<size_t> (i)] = (a + 2.0f * b + c) * 0.25f;
        }

        // Time-domain smoothing. Update at most once per route per paint tick even if
        // multiple event-snapshot bodies for the same route are rendered.
        const unsigned long long eqNowMs = GetTickCount64 ();
        auto& eqLastMs = routeEqStableLastMs[routeIndex];
        if (eqLastMs == 0ull)
            eqLastMs = eqNowMs;
        else if (routeHasSignal[routeIndex].load (std::memory_order_relaxed) && eqNowMs > eqLastMs)
        {
            const float dtMs = static_cast<float> (std::min<unsigned long long> (80ull, eqNowMs - eqLastMs));
            const float alpha = 1.0f - std::exp (-dtMs / 360.0f);
            for (int i = 0; i < kBands; ++i)
            {
                float& stable = routeEqStableDb[routeIndex][static_cast<size_t> (i)];
                const float target = targetEqDeltaDb[static_cast<size_t> (i)];
                stable += (target - stable) * alpha;
                if (std::abs (stable) < 0.20f && std::abs (target) < 0.20f)
                    stable = 0.0f;
            }
            eqLastMs = eqNowMs;
        }

        // Require a coherent local region: self + at least two nearby bands with the
        // same sign. Isolated moving harmonics/formants therefore do not deform the body.
        for (int i = 0; i < kBands; ++i)
        {
            const float stable = routeEqStableDb[routeIndex][static_cast<size_t> (i)];
            int supporters = 0;
            if (std::abs (stable) >= 2.40f)
            {
                for (int j = std::max (0, i - 2); j <= std::min (kBands - 1, i + 2); ++j)
                {
                    const float neighbour = routeEqStableDb[routeIndex][static_cast<size_t> (j)];
                    if (stable * neighbour > 0.0f && std::abs (neighbour) >= 1.80f)
                        ++supporters;
                }
            }
            eqDeltaDb[static_cast<size_t> (i)] = supporters >= 3 ? stable : 0.0f;

            // V0.28 used 1.8x visual gain. Reduce this slightly now that the signal is
            // stable: readable but not twitchy/overblown.
            const float visualDelta = std::clamp (eqDeltaDb[static_cast<size_t> (i)] * 1.25f,
                -11.0f, 11.0f);
            shape[static_cast<size_t> (i)] = clamp01 (
                baseShape[static_cast<size_t> (i)] + visualDelta / 32.0f);
        }

        int strongestEqBand = -1;
        float strongestEqDelta = 0.0f;
        for (int i = 0; i < kBands; ++i)
        {
            const float d = eqDeltaDb[static_cast<size_t> (i)];
            if (std::abs (d) > std::abs (strongestEqDelta))
            {
                strongestEqDelta = d;
                strongestEqBand = i;
            }
        }

        // Candidate must remain in roughly the same frequency neighbourhood for 260 ms
        // before it becomes the displayed EQ badge. Once displayed, hold the frequency
        // for at least 500 ms so the label cannot jump on every FFT update.
        const int candidateCode = std::abs (strongestEqDelta) >= 3.0f ? strongestEqBand + 1 : 0;
        int& storedCandidateCode = routeEqCandidateCode[routeIndex];
        auto& candidateSince = routeEqCandidateSinceMs[routeIndex];
        if (candidateCode == 0)
        {
            storedCandidateCode = 0;
            candidateSince = eqNowMs;
        }
        else
        {
            const int storedCandidateBand = storedCandidateCode > 0 ? storedCandidateCode - 1 : -100;
            if (storedCandidateCode == 0 || std::abs (strongestEqBand - storedCandidateBand) > 3)
            {
                storedCandidateCode = candidateCode;
                candidateSince = eqNowMs;
            }
            else if (eqNowMs >= candidateSince + 260ull)
            {
                int& badgeCode = routeEqBadgeCode[routeIndex];
                float& badgeDelta = routeEqBadgeDelta[routeIndex];
                auto& badgeHoldUntil = routeEqBadgeHoldUntilMs[routeIndex];
                const int badgeBand = badgeCode > 0 ? badgeCode - 1 : -100;
                if (badgeCode == 0)
                {
                    badgeCode = storedCandidateCode;
                    badgeDelta = strongestEqDelta;
                    badgeHoldUntil = eqNowMs + 500ull;
                }
                else if (std::abs (strongestEqBand - badgeBand) <= 4)
                {
                    const float sameRegionDelta = eqDeltaDb[static_cast<size_t> (std::clamp (badgeBand, 0, kBands - 1))];
                    const float targetBadgeDelta = std::abs (sameRegionDelta) >= 1.5f
                        ? sameRegionDelta : strongestEqDelta;
                    badgeDelta += (targetBadgeDelta - badgeDelta) * 0.16f;
                }
                else if (eqNowMs >= badgeHoldUntil)
                {
                    badgeCode = storedCandidateCode;
                    badgeDelta = strongestEqDelta;
                    badgeHoldUntil = eqNowMs + 500ull;
                }
            }
        }

        if (routeEqBadgeCode[routeIndex] != 0 && candidateCode == 0 &&
            eqNowMs >= routeEqBadgeHoldUntilMs[routeIndex])
        {
            routeEqBadgeCode[routeIndex] = 0;
            routeEqBadgeDelta[routeIndex] = 0.0f;
        }

        const int displayEqBand = routeEqBadgeCode[routeIndex] > 0
            ? routeEqBadgeCode[routeIndex] - 1 : -1;
        const float displayEqDelta = routeEqBadgeDelta[routeIndex];
        if (displayEqBand >= 0 && displayEqBand < kBands)
        {
            routeEqDiagHz[routeIndex].store (
                bandHz[static_cast<size_t> (displayEqBand)].load (std::memory_order_relaxed),
                std::memory_order_relaxed);
            routeEqDiagDb[routeIndex].store (displayEqDelta, std::memory_order_relaxed);
        }
        else
        {
            routeEqDiagHz[routeIndex].store (0.0f, std::memory_order_relaxed);
            routeEqDiagDb[routeIndex].store (0.0f, std::memory_order_relaxed);
        }

'''
replace_between(
    "        std::array<float, kBands> baseShape {};",
    "        std::vector<std::pair<int, int>> rawRuns;",
    stable_delta,
    "stable EQ delta calculation",
)

# Existing comment mentions V0.28's aggressive live delta.
text = text.replace(
    "const float s = shape[static_cast<size_t> (band)]; // V0.28 base + exaggerated live EQ delta",
    "const float s = shape[static_cast<size_t> (band)]; // V0.29 stable base + temporally confirmed EQ delta"
)

# -----------------------------------------------------------------------------
# Replace V0.28 overlay/badge with the stable, held selection calculated above.
stable_overlay = r'''        // V0.29 stable EQ overlay: only coherent, temporally confirmed bands.
        if (displayEqBand >= 0 && std::abs (displayEqDelta) >= 2.0f)
        {
            const COLORREF eqGlow = mixColor (raw, RGB (248, 252, 255), 0.24f);
            HPEN eqPen = CreatePen (PS_SOLID, 2, eqGlow);
            oldPen = SelectObject (dc, eqPen);
            oldBrush = SelectObject (dc, GetStockObject (NULL_BRUSH));
            for (const auto& lobe : lobes)
            {
                int parity = 0;
                for (int i = lobe.first; i <= lobe.second; ++i)
                {
                    if (std::abs (eqDeltaDb[static_cast<size_t> (i)]) < 2.40f)
                        continue;
                    if ((parity++ & 1) != 0)
                        continue;
                    if (radiusForBand (i, 1.0f) <= 0.0f)
                        continue;
                    const auto ring = makeRing (i, 1.025f, 0.0f, false);
                    Polyline (dc, ring.data (), static_cast<int> (ring.size ()));
                }
            }
            SelectObject (dc, oldBrush);
            SelectObject (dc, oldPen);
            DeleteObject (eqPen);

            const float hz = bandHz[static_cast<size_t> (displayEqBand)].load (std::memory_order_relaxed);
            const float rx = std::max (0.025f, radiusForBand (displayEqBand, 1.08f));
            const auto anchor = projectWorld (
                track.balance + rx, roomYForFrequency (hz), track.visualZ, area);
            wchar_t badge[64] {};
            if (hz >= 1000.0f)
                swprintf_s (badge, L"EQ %+.1f dB @ %.1fk", displayEqDelta, hz / 1000.0f);
            else
                swprintf_s (badge, L"EQ %+.1f dB @ %.0f Hz", displayEqDelta, hz);

            SIZE sz {};
            GetTextExtentPoint32W (dc, badge, static_cast<int> (wcslen (badge)), &sz);
            RECT br {anchor.x + 8, anchor.y - 10, anchor.x + 22 + sz.cx, anchor.y + 12};
            HBRUSH badgeBrush = CreateSolidBrush (mixColor (raw, roomBg, 0.76f));
            FillRect (dc, &br, badgeBrush);
            DeleteObject (badgeBrush);
            SetBkMode (dc, TRANSPARENT);
            SetTextColor (dc, RGB (242, 248, 255));
            RECT tr {br.left + 6, br.top, br.right - 4, br.bottom};
            DrawTextW (dc, badge, -1, &tr, DT_LEFT | DT_SINGLELINE | DT_VCENTER);
        }

'''
replace_between(
    "        // V0.28 EQ delta overlay: bright local contour + explicit dB/frequency badge.\n",
    "        // Lobe silhouette closes one band outside the run, matching web lobePath().\n",
    stable_overlay,
    "stable EQ overlay",
)

# -----------------------------------------------------------------------------
# Diagnostics: add the held badge frequency/delta so the next CSV can quantify
# whether the frequency indicator is still jumping.
old_header = "tick_ms,route,name,block_ms,render_ms,render_pct,paint_ms,peak_db,fast_rms_db,presence,learned_loud_db,z,profile_ready,dominant_hz,low_hz,high_hz,onset_count,onset_to_presence_ms,onset_to_profile_ms,onset_to_draw_ms,voice_count,voice_pan_0,voice_pan_1,voice_pan_2,live_pan,live_width,depth_level_db,pan_shift,x_sens,z_sens,disappear_ms\\n"
new_header = "tick_ms,route,name,block_ms,render_ms,render_pct,paint_ms,peak_db,fast_rms_db,presence,learned_loud_db,z,profile_ready,dominant_hz,low_hz,high_hz,onset_count,onset_to_presence_ms,onset_to_profile_ms,onset_to_draw_ms,voice_count,voice_pan_0,voice_pan_1,voice_pan_2,live_pan,live_width,depth_level_db,pan_shift,x_sens,z_sens,disappear_ms,eq_hz,eq_db\\n"
replace_once(old_header, new_header, "EQ diagnostics header")

old_fmt = "%llu,%d,%s,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.4f,%.2f,%.4f,%d,%.1f,%.1f,%.1f,%u,%.1f,%.1f,%.1f,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%.4f,%.2f,%.2f,%.0f\\n"
new_fmt = "%llu,%d,%s,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.4f,%.2f,%.4f,%d,%.1f,%.1f,%.1f,%u,%.1f,%.1f,%.1f,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%.4f,%.2f,%.2f,%.0f,%.1f,%.2f\\n"
replace_once(old_fmt, new_fmt, "EQ diagnostics format")

old_tail = "                xAxisSensitivity,\n                zAxisSensitivity,\n                disappearTimeMs);"
new_tail = "                xAxisSensitivity,\n                zAxisSensitivity,\n                disappearTimeMs,\n                routeEqDiagHz[idx].load (std::memory_order_relaxed),\n                routeEqDiagDb[idx].load (std::memory_order_relaxed));"
replace_once(old_tail, new_tail, "EQ diagnostics tail")

text = text.replace(
    "V0.28 readable EQ: stable identity + exaggerated live spectral delta + local badge",
    "V0.29 stable EQ: level-normalized + 360ms smoothing + coherent bands + badge hysteresis"
)

out.write_text(text, encoding="utf-8")
print(out)
