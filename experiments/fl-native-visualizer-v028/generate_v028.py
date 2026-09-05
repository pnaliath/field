from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v027 = root / "fl-native-visualizer-v027"

# Start from compile-green V0.27: stable learned width + calibrated X/Z + disappear slider.
runpy.run_path(str(v027 / "generate_v027.py"), run_name="__main__")
src = v027 / "generated" / "fieldv027.cpp"
out = here / "generated" / "fieldv028.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.28 could not find patch point: {label}")
    text = text.replace(old, new, 1)


# Identity + latest calibrated transient lifetime.
text = text.replace("Field V0.27", "Field V0.28")
text = text.replace("FieldV027", "FieldV028")
text = text.replace("V027", "V028")
text = text.replace("v027", "v028")
text = text.replace("FieldV027_diagnostics.csv", "FieldV028_diagnostics.csv")
text = text.replace("STABLE WIDTH + DISAPPEAR TEST", "READABLE EQ DELTA")
text = text.replace("float disappearTimeMs = 440.0f;", "float disappearTimeMs = 500.0f;", 1)

# -----------------------------------------------------------------------------
# Current FFT-frame spectrum, separate from the long-term 82nd-percentile identity.
# The long-term profile remains the body baseline. The current frame is used only
# to show spectral change (EQ boosts/cuts) clearly and quickly.
replace_once(
    "    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeProfileDb;\n",
    "    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeProfileDb;\n"
    "    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeLiveSpectrumDb;\n",
    "live spectrum state",
)

replace_once(
    "        for (auto& route : routeProfileDb)\n"
    "            for (auto& band : route)\n"
    "                band.store (-120.0f, std::memory_order_relaxed);",
    "        for (auto& route : routeProfileDb)\n"
    "            for (auto& band : route)\n"
    "                band.store (-120.0f, std::memory_order_relaxed);\n"
    "        for (auto& route : routeLiveSpectrumDb)\n"
    "            for (auto& band : route)\n"
    "                band.store (-120.0f, std::memory_order_relaxed);",
    "live spectrum initialization",
)

# V0.20's long-window FFT already computes percentileInputDb[] for the CURRENT frame.
# Publish it before feeding the long-term histogram.
replace_once(
    "        // Feed the same long-term 82nd-percentile learner used by the web-style body.\n",
    "        // Publish the current FFT frame for V0.28 EQ-delta rendering.\n"
    "        for (int band = 0; band < kBands; ++band)\n"
    "            routeLiveSpectrumDb[routeIndex][static_cast<size_t> (band)].store (\n"
    "                percentileInputDb[static_cast<size_t> (band)], std::memory_order_relaxed);\n\n"
    "        // Feed the same long-term 82nd-percentile learner used by the web-style body.\n",
    "publish current spectrum frame",
)

# -----------------------------------------------------------------------------
# Build an EQ delta in drawSpectralBody(): current frame minus learned identity.
# 1.25 dB dead-zone suppresses natural microscopic variation. 1-2-1 smoothing keeps
# the highlight shaped like an EQ band instead of individual FFT-bin chatter.
replace_once(
    "        std::array<float, kBands> shape {};\n"
    "        for (int i = 0; i < kBands; ++i)\n"
    "            shape[static_cast<size_t> (i)] = learnedShapeEnergy (routeIndex, i);",
    "        std::array<float, kBands> baseShape {};\n"
    "        std::array<float, kBands> rawEqDeltaDb {};\n"
    "        std::array<float, kBands> eqDeltaDb {};\n"
    "        std::array<float, kBands> shape {};\n"
    "        for (int i = 0; i < kBands; ++i)\n"
    "        {\n"
    "            baseShape[static_cast<size_t> (i)] = learnedShapeEnergy (routeIndex, i);\n"
    "            const float learnedDb = routeProfileDb[routeIndex][static_cast<size_t> (i)].load (\n"
    "                std::memory_order_relaxed);\n"
    "            const float liveDb = routeLiveSpectrumDb[routeIndex][static_cast<size_t> (i)].load (\n"
    "                std::memory_order_relaxed);\n"
    "            float delta = std::clamp (liveDb - learnedDb, -12.0f, 12.0f);\n"
    "            if (std::abs (delta) < 1.25f) delta = 0.0f;\n"
    "            rawEqDeltaDb[static_cast<size_t> (i)] = delta;\n"
    "        }\n"
    "        for (int i = 0; i < kBands; ++i)\n"
    "        {\n"
    "            const float a = rawEqDeltaDb[static_cast<size_t> (std::max (0, i - 1))];\n"
    "            const float b = rawEqDeltaDb[static_cast<size_t> (i)];\n"
    "            const float c = rawEqDeltaDb[static_cast<size_t> (std::min (kBands - 1, i + 1))];\n"
    "            const float delta = (a + 2.0f * b + c) * 0.25f;\n"
    "            eqDeltaDb[static_cast<size_t> (i)] = delta;\n"
    "            // Visual exaggeration only: measured dB remains real. A +/-6 dB EQ move\n"
    "            // produces a large, readable local bulge/notch instead of disappearing\n"
    "            // inside the source's already-large absolute spectrum.\n"
    "            const float visualDelta = std::clamp (delta * 1.80f, -18.0f, 18.0f);\n"
    "            shape[static_cast<size_t> (i)] = clamp01 (\n"
    "                baseShape[static_cast<size_t> (i)] + visualDelta / 28.0f);\n"
    "        }",
    "EQ delta geometry",
)

# Make the radius use the EQ-deformed shape. (It already reads shape[]; keep this
# explicit comment in generated code so the contract remains obvious.)
replace_once(
    "            const float s = shape[static_cast<size_t> (band)];\n",
    "            const float s = shape[static_cast<size_t> (band)]; // V0.28 base + exaggerated live EQ delta\n",
    "EQ-deformed radius",
)

# -----------------------------------------------------------------------------
# Highlight changed frequency bands immediately before the normal silhouette.
# Draw only meaningful deltas (>2 dB), every second affected band to keep density low.
# A badge on the strongest changed band makes the frequency and direction explicit.
eq_overlay = r'''        // V0.28 EQ delta overlay: bright local contour + explicit dB/frequency badge.
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

        if (std::abs (strongestEqDelta) >= 2.0f)
        {
            const COLORREF eqGlow = mixColor (raw, RGB (248, 252, 255), 0.18f);
            HPEN eqPen = CreatePen (PS_SOLID, 2, eqGlow);
            oldPen = SelectObject (dc, eqPen);
            oldBrush = SelectObject (dc, GetStockObject (NULL_BRUSH));
            for (const auto& lobe : lobes)
            {
                int parity = 0;
                for (int i = lobe.first; i <= lobe.second; ++i)
                {
                    if (std::abs (eqDeltaDb[static_cast<size_t> (i)]) < 2.0f)
                        continue;
                    if ((parity++ & 1) != 0)
                        continue;
                    if (radiusForBand (i, 1.0f) <= 0.0f)
                        continue;
                    const auto ring = makeRing (i, 1.035f, 0.0f, false);
                    Polyline (dc, ring.data (), static_cast<int> (ring.size ()));
                }
            }
            SelectObject (dc, oldBrush);
            SelectObject (dc, oldPen);
            DeleteObject (eqPen);

            // Put a compact badge just outside the modified contour. This is deliberately
            // literal: the user should not have to infer where a bell EQ is acting.
            if (strongestEqBand >= 0)
            {
                const float hz = bandHz[static_cast<size_t> (strongestEqBand)].load (std::memory_order_relaxed);
                const float rx = std::max (0.025f, radiusForBand (strongestEqBand, 1.10f));
                const auto anchor = projectWorld (
                    track.balance + rx, roomYForFrequency (hz), track.visualZ, area);
                wchar_t badge[64] {};
                if (hz >= 1000.0f)
                    swprintf_s (badge, L"EQ %+.1f dB @ %.1fk", strongestEqDelta, hz / 1000.0f);
                else
                    swprintf_s (badge, L"EQ %+.1f dB @ %.0f Hz", strongestEqDelta, hz);

                SIZE sz {};
                GetTextExtentPoint32W (dc, badge, static_cast<int> (wcslen (badge)), &sz);
                RECT br {anchor.x + 8, anchor.y - 10, anchor.x + 22 + sz.cx, anchor.y + 12};
                HBRUSH badgeBrush = CreateSolidBrush (mixColor (raw, roomBg, 0.72f));
                FillRect (dc, &br, badgeBrush);
                DeleteObject (badgeBrush);
                SetBkMode (dc, TRANSPARENT);
                SetTextColor (dc, RGB (242, 248, 255));
                RECT tr {br.left + 6, br.top, br.right - 4, br.bottom};
                DrawTextW (dc, badge, -1, &tr, DT_LEFT | DT_SINGLELINE | DT_VCENTER);
            }
        }

'''
replace_once(
    "        // Lobe silhouette closes one band outside the run, matching web lobePath().\n",
    eq_overlay + "        // Lobe silhouette closes one band outside the run, matching web lobePath().\n",
    "EQ delta overlay",
)

text = text.replace(
    "V0.27 stable learned width + testable transient disappear lifetime",
    "V0.28 readable EQ: stable identity + exaggerated live spectral delta + local badge"
)

out.write_text(text, encoding="utf-8")
print(out)
