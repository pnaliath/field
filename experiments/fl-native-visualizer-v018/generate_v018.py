from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v017 = root / "fl-native-visualizer-v017"

# Start from the compile-green V0.17 web-lobe build.
runpy.run_path(str(v017 / "generate_v017_fixed.py"), run_name="__main__")
src = v017 / "generated" / "fieldv017.cpp"
out = here / "generated" / "fieldv018.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.18 could not find patch point: {label}")
    text = text.replace(old, new, 1)


# Fresh identity.
text = text.replace("Field V0.17", "Field V0.18")
text = text.replace("FieldV017", "FieldV018")
text = text.replace("V017", "V018")
text = text.replace("v017", "v018")
text = text.replace("WEB LOBE VISUALIZER", "RESPONSE DIAGNOSTICS")

# -----------------------------------------------------------------------------
# Diagnostic state. Audio-thread writes are atomics only; file I/O is UI-thread
# only and throttled. The goal is to separate raw-input response, presence response,
# learned-profile response, Z response and actual first paint response.
replace_once(
    "    std::array<std::atomic<float>, kMaxRoutes> routeVisualPresence;\n",
    "    std::array<std::atomic<float>, kMaxRoutes> routeVisualPresence;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> diagFastRmsDb;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> diagVisualZ;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> diagPresenceDelayMs;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> diagDrawDelayMs;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> diagProfileDelayMs;\n"
    "    std::array<std::atomic<unsigned long long>, kMaxRoutes> diagOnsetMs;\n"
    "    std::array<std::atomic<unsigned int>, kMaxRoutes> diagOnsetCount;\n"
    "    std::array<bool, kMaxRoutes> diagSignalLatched {};\n"
    "    std::atomic<float> diagBlockMs {0.0f};\n"
    "    std::atomic<float> diagRenderMs {0.0f};\n"
    "    std::atomic<float> diagPaintIntervalMs {0.0f};\n"
    "    unsigned long long diagLastPaintTick = 0;\n"
    "    unsigned long long diagLastLogTick = 0;\n"
    "    LARGE_INTEGER diagPerfFrequency {};\n"
    "    std::wstring diagLogPath;\n",
    "diagnostic state members",
)

replace_once(
    "        for (auto& presence : routeVisualPresence)\n"
    "            presence.store (0.0f, std::memory_order_relaxed);",
    "        for (auto& presence : routeVisualPresence)\n"
    "            presence.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagFastRmsDb) v.store (-120.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagVisualZ) v.store (0.5f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagPresenceDelayMs) v.store (-1.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagDrawDelayMs) v.store (-1.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagProfileDelayMs) v.store (-1.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagOnsetMs) v.store (0ull, std::memory_order_relaxed);\n"
    "        for (auto& v : diagOnsetCount) v.store (0u, std::memory_order_relaxed);\n"
    "        QueryPerformanceFrequency (&diagPerfFrequency);\n"
    "        initializeDiagnosticsLog ();",
    "diagnostic initialization",
)

# -----------------------------------------------------------------------------
# Audio callback timing budget. This tells us whether the analyzer itself is close
# to overrunning the host block, which would feel like real audio latency/glitching.
replace_once(
    "        if (!dest || length <= 0)\n            return;\n\n        float refRms",
    "        if (!dest || length <= 0)\n"
    "            return;\n\n"
    "        LARGE_INTEGER diagRenderStart {};\n"
    "        QueryPerformanceCounter (&diagRenderStart);\n"
    "        const float diagSr = std::max (8000.0f, sampleRate.load (std::memory_order_relaxed));\n"
    "        diagBlockMs.store (1000.0f * static_cast<float> (length) / diagSr, std::memory_order_relaxed);\n\n"
    "        float refRms",
    "audio callback timer start",
)

# Existing stereo sums give us a fast RMS for free; no extra analyser pass.
replace_once(
    "            const float width = clamp01 (static_cast<float> ((side / (mid + side + 1.0e-12)) * 1.65));\n\n"
    "            const float targetPeakDb",
    "            const float width = clamp01 (static_cast<float> ((side / (mid + side + 1.0e-12)) * 1.65));\n"
    "            const double fastRms = std::sqrt ((sumL2 + sumR2) / static_cast<double> (std::max (1, length * 2)));\n"
    "            diagFastRmsDb[routeArrayIndex].store (linearToDb (fastRms), std::memory_order_relaxed);\n\n"
    "            const float targetPeakDb",
    "fast RMS telemetry",
)

# Onset -> presence/profile timing. Hysteresis prevents a sustained note from
# creating an event every block. These timings do no file I/O on the audio thread.
replace_once(
    "                presenceCell.store (clamp01 (oldPresence + (targetPresence - oldPresence) * coefficient),\n"
    "                    std::memory_order_relaxed);\n"
    "            }\n"
    "            if (hasSignal)",
    "                presenceCell.store (clamp01 (oldPresence + (targetPresence - oldPresence) * coefficient),\n"
    "                    std::memory_order_relaxed);\n"
    "            }\n"
    "            {\n"
    "                const bool diagNow = targetPeakDb > -72.0f;\n"
    "                if (diagNow && !diagSignalLatched[routeArrayIndex])\n"
    "                {\n"
    "                    diagSignalLatched[routeArrayIndex] = true;\n"
    "                    const unsigned long long now = GetTickCount64 ();\n"
    "                    diagOnsetMs[routeArrayIndex].store (now, std::memory_order_relaxed);\n"
    "                    diagOnsetCount[routeArrayIndex].fetch_add (1u, std::memory_order_relaxed);\n"
    "                    diagPresenceDelayMs[routeArrayIndex].store (-1.0f, std::memory_order_relaxed);\n"
    "                    diagDrawDelayMs[routeArrayIndex].store (-1.0f, std::memory_order_relaxed);\n"
    "                    diagProfileDelayMs[routeArrayIndex].store (\n"
    "                        routeProfileReady[routeArrayIndex].load (std::memory_order_relaxed) ? 0.0f : -1.0f,\n"
    "                        std::memory_order_relaxed);\n"
    "                }\n"
    "                else if (!diagNow && targetPeakDb < -84.0f)\n"
    "                    diagSignalLatched[routeArrayIndex] = false;\n\n"
    "                const unsigned long long onset = diagOnsetMs[routeArrayIndex].load (std::memory_order_relaxed);\n"
    "                if (onset != 0ull)\n"
    "                {\n"
    "                    const unsigned long long now = GetTickCount64 ();\n"
    "                    if (diagPresenceDelayMs[routeArrayIndex].load (std::memory_order_relaxed) < 0.0f &&\n"
    "                        routeVisualPresence[routeArrayIndex].load (std::memory_order_relaxed) >= 0.08f)\n"
    "                        diagPresenceDelayMs[routeArrayIndex].store (static_cast<float> (now - onset), std::memory_order_relaxed);\n"
    "                    if (diagProfileDelayMs[routeArrayIndex].load (std::memory_order_relaxed) < 0.0f &&\n"
    "                        routeProfileReady[routeArrayIndex].load (std::memory_order_relaxed))\n"
    "                        diagProfileDelayMs[routeArrayIndex].store (static_cast<float> (now - onset), std::memory_order_relaxed);\n"
    "                }\n"
    "            }\n"
    "            if (hasSignal)",
    "onset response telemetry",
)

# Record the actual derived Z used by the renderer.
replace_once(
    "            track.visualZ = std::clamp (smoothDepth, 0.12f, 0.90f);\n"
    "            const float frontness",
    "            track.visualZ = std::clamp (smoothDepth, 0.12f, 0.90f);\n"
    "            diagVisualZ[idx].store (track.visualZ, std::memory_order_relaxed);\n"
    "            const float frontness",
    "diagnostic visual Z",
)

# First actual body draw after an onset: this is the end-to-end visual response.
replace_once(
    "        const float presence = visualPresenceForTrack (track);\n"
    "        if (presence <= 0.012f)\n"
    "            return;\n\n"
    "        const COLORREF raw",
    "        const float presence = visualPresenceForTrack (track);\n"
    "        if (presence <= 0.012f)\n"
    "            return;\n"
    "        stampDiagnosticDraw (routeIndex);\n\n"
    "        const COLORREF raw",
    "first painted body timing",
)

# Typical FIELD mode render cost. The diagnostics build is meant to be used in Field mode.
replace_once(
    "            std::memcpy (dest, recon, static_cast<size_t> (length) * sizeof (TWAV32FS));\n"
    "            return;",
    "            std::memcpy (dest, recon, static_cast<size_t> (length) * sizeof (TWAV32FS));\n"
    "            recordDiagnosticRenderCost (diagRenderStart);\n"
    "            return;",
    "field render cost",
)

# -----------------------------------------------------------------------------
# UI-side helpers: compact overlay + 2 Hz CSV log in %TEMP%. This is deliberately
# off the audio thread. Send this CSV back after reproducing the lag and we can plot
# raw input vs fast RMS vs learned loudness vs Z vs first draw for every route.
diag_helpers = r'''    void initializeDiagnosticsLog ()
    {
        wchar_t tempPath[MAX_PATH] {};
        const DWORD n = GetTempPathW (MAX_PATH, tempPath);
        if (n == 0 || n >= MAX_PATH)
            diagLogPath = L"FieldV018_diagnostics.csv";
        else
            diagLogPath = std::wstring (tempPath) + L"FieldV018_diagnostics.csv";

        FILE* f = nullptr;
        if (_wfopen_s (&f, diagLogPath.c_str (), L"w") == 0 && f)
        {
            std::fprintf (f,
                "tick_ms,route,name,block_ms,render_ms,render_pct,paint_ms,peak_db,fast_rms_db,presence,learned_loud_db,z,profile_ready,dominant_hz,low_hz,high_hz,onset_count,onset_to_presence_ms,onset_to_profile_ms,onset_to_draw_ms\n");
            std::fclose (f);
        }
    }

    void recordDiagnosticRenderCost (const LARGE_INTEGER& start)
    {
        LARGE_INTEGER end {};
        QueryPerformanceCounter (&end);
        const double freq = static_cast<double> (std::max<LONGLONG> (1, diagPerfFrequency.QuadPart));
        const float ms = static_cast<float> ((static_cast<double> (end.QuadPart - start.QuadPart) * 1000.0) / freq);
        diagRenderMs.store (ms, std::memory_order_relaxed);
    }

    void stampDiagnosticDraw (size_t routeIndex)
    {
        if (routeIndex >= kMaxRoutes)
            return;
        if (diagDrawDelayMs[routeIndex].load (std::memory_order_relaxed) >= 0.0f)
            return;
        const unsigned long long onset = diagOnsetMs[routeIndex].load (std::memory_order_relaxed);
        if (onset == 0ull)
            return;
        const unsigned long long now = GetTickCount64 ();
        diagDrawDelayMs[routeIndex].store (static_cast<float> (now - onset), std::memory_order_relaxed);
    }

    void updateDiagnosticPaintClock ()
    {
        const unsigned long long now = GetTickCount64 ();
        if (diagLastPaintTick != 0ull)
            diagPaintIntervalMs.store (static_cast<float> (now - diagLastPaintTick), std::memory_order_relaxed);
        diagLastPaintTick = now;
    }

    std::string diagnosticNameForRoute (int route) const
    {
        for (const auto& item : inputs)
        {
            if (item.routeIndex != route)
                continue;
            std::string s = !item.visibleName.empty () ? item.visibleName : item.userName;
            if (s.empty ()) s = "Track_" + std::to_string (item.mixerIndex >= 0 ? item.mixerIndex : route);
            for (char& c : s)
                if (c == ',' || c == '"' || c == '\r' || c == '\n' || c == '\t') c = '_';
            return s;
        }
        return "Route_" + std::to_string (route);
    }

    void maybeWriteDiagnostics ()
    {
        const unsigned long long now = GetTickCount64 ();
        if (now - diagLastLogTick < 500ull)
            return;
        diagLastLogTick = now;

        FILE* f = nullptr;
        if (_wfopen_s (&f, diagLogPath.c_str (), L"a") != 0 || !f)
            return;

        const int count = std::clamp (reportedRouteCount.load (std::memory_order_relaxed), 0, kMaxRoutes);
        const float blockMs = diagBlockMs.load (std::memory_order_relaxed);
        const float renderMs = diagRenderMs.load (std::memory_order_relaxed);
        const float renderPct = blockMs > 0.01f ? renderMs / blockMs * 100.0f : 0.0f;
        const float paintMs = diagPaintIntervalMs.load (std::memory_order_relaxed);

        for (int route = 1; route <= count; ++route)
        {
            const size_t idx = static_cast<size_t> (route - 1);
            if (!everActive[idx].load (std::memory_order_relaxed))
                continue;

            float best = 0.0f;
            float dominantHz = 0.0f;
            float lowHz = 0.0f;
            float highHz = 0.0f;
            for (int band = 0; band < kBands; ++band)
            {
                const float e = learnedShapeEnergy (idx, band);
                const float hz = bandHz[static_cast<size_t> (band)].load (std::memory_order_relaxed);
                if (e > kShapeGate)
                {
                    if (lowHz <= 0.0f) lowHz = hz;
                    highHz = hz;
                }
                if (e > best)
                {
                    best = e;
                    dominantHz = hz;
                }
            }

            const std::string name = diagnosticNameForRoute (route);
            std::fprintf (f,
                "%llu,%d,%s,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.4f,%.2f,%.4f,%d,%.1f,%.1f,%.1f,%u,%.1f,%.1f,%.1f\n",
                now, route, name.c_str (), blockMs, renderMs, renderPct, paintMs,
                routePeakDb[idx].load (std::memory_order_relaxed),
                diagFastRmsDb[idx].load (std::memory_order_relaxed),
                routeVisualPresence[idx].load (std::memory_order_relaxed),
                routeLoudnessDb[idx].load (std::memory_order_relaxed),
                diagVisualZ[idx].load (std::memory_order_relaxed),
                routeProfileReady[idx].load (std::memory_order_relaxed) ? 1 : 0,
                dominantHz, lowHz, highHz,
                diagOnsetCount[idx].load (std::memory_order_relaxed),
                diagPresenceDelayMs[idx].load (std::memory_order_relaxed),
                diagProfileDelayMs[idx].load (std::memory_order_relaxed),
                diagDrawDelayMs[idx].load (std::memory_order_relaxed));
        }
        std::fclose (f);
    }

    void drawDiagnosticsOverlay (HDC dc, const RECT& client)
    {
        const float blockMs = diagBlockMs.load (std::memory_order_relaxed);
        const float renderMs = diagRenderMs.load (std::memory_order_relaxed);
        const float renderPct = blockMs > 0.01f ? renderMs / blockMs * 100.0f : 0.0f;
        const float paintMs = diagPaintIntervalMs.load (std::memory_order_relaxed);
        const float fftCadence = blockMs * 4.0f;

        float worstDraw = -1.0f;
        int worstRoute = 0;
        for (int i = 0; i < kMaxRoutes; ++i)
        {
            const float d = diagDrawDelayMs[static_cast<size_t> (i)].load (std::memory_order_relaxed);
            if (d > worstDraw) { worstDraw = d; worstRoute = i + 1; }
        }

        wchar_t line1[512] {};
        swprintf_s (line1,
            L"DIAG  block %.2f ms | Field CPU %.2f ms (%.0f%%) | paint %.0f ms | spectrum cadence <= %.1f ms",
            blockMs, renderMs, renderPct, paintMs, fftCadence);
        wchar_t line2[512] {};
        if (worstRoute > 0)
            swprintf_s (line2, L"Worst last onset->draw: route %d = %.0f ms   |   log: %%TEMP%%\\FieldV018_diagnostics.csv",
                worstRoute, worstDraw);
        else
            swprintf_s (line2, L"Play a track to capture response latency   |   log: %%TEMP%%\\FieldV018_diagnostics.csv");

        RECT box {client.left + 14, client.bottom - 62, client.right - 14, client.bottom - 10};
        HBRUSH brush = CreateSolidBrush (RGB (11, 15, 21));
        FillRect (dc, &box, brush);
        DeleteObject (brush);
        HPEN pen = CreatePen (PS_SOLID, 1, RGB (56, 74, 94));
        auto oldPen = SelectObject (dc, pen);
        auto oldBrush = SelectObject (dc, GetStockObject (NULL_BRUSH));
        Rectangle (dc, box.left, box.top, box.right, box.bottom);
        SelectObject (dc, oldBrush); SelectObject (dc, oldPen); DeleteObject (pen);

        HFONT font = CreateFontW (-13, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, FIXED_PITCH, L"Consolas");
        auto oldFont = SelectObject (dc, font);
        SetBkMode (dc, TRANSPARENT);
        SetTextColor (dc, renderPct > 70.0f ? RGB (244, 119, 119) : RGB (150, 205, 224));
        RECT r1 {box.left + 10, box.top + 4, box.right - 10, box.top + 25};
        DrawTextW (dc, line1, -1, &r1, DT_LEFT | DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);
        SetTextColor (dc, RGB (128, 148, 169));
        RECT r2 {box.left + 10, box.top + 25, box.right - 10, box.bottom - 3};
        DrawTextW (dc, line2, -1, &r2, DT_LEFT | DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);
        SelectObject (dc, oldFont);
        DeleteObject (font);
    }

'''
replace_once(
    "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)\n    {",
    diag_helpers + "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)\n    {",
    "diagnostic UI helpers",
)

# Paint cadence and final overlay/log call.
replace_once(
    "        HDC dc = BeginPaint (hwnd, &ps);\n",
    "        HDC dc = BeginPaint (hwnd, &ps);\n"
    "        updateDiagnosticPaintClock ();\n",
    "paint cadence timestamp",
)
replace_once(
    "        EndPaint (hwnd, &ps);",
    "        maybeWriteDiagnostics ();\n"
    "        drawDiagnosticsOverlay (dc, client);\n"
    "        EndPaint (hwnd, &ps);",
    "diagnostic overlay and logger",
)

text = text.replace(
    "Web-style lobes: occupied frequencies only, absolute per-track Z, held presence, stacked 3D rings.",
    "V0.18 diagnostics: raw audio, fast RMS, presence, learned loudness, Z and first-draw timing are logged separately."
)

out.write_text(text, encoding="utf-8")
print(out)
