from pathlib import Path

src = Path(__file__).resolve().parents[1] / "fl-native-visualizer-v004" / "source" / "fieldv004.cpp"
out = Path(__file__).resolve().parent / "generated" / "fieldv005.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")

# Fresh plugin identity so FL Studio treats this as a separate test build.
text = text.replace("Field V0.04 Visualizer", "Field V0.05 Stable Visualizer")
text = text.replace("FieldV004", "FieldV005")
text = text.replace("V0.04", "V0.05")
text = text.replace("V004", "V005")

# Analyse spectrum less often. Audio is still processed every block; only visual telemetry slows down.
text = text.replace(
    "const bool doSpectrum = ((++analysisBlockCounter & 1u) == 0u);",
    "const bool doSpectrum = ((++analysisBlockCounter & 3u) == 0u);"
)

# Do not hard-reset visual peaks every block. Let silent/inactive tracks decay smoothly.
text = text.replace(
    "for (int route = 0; route < count; ++route)\n            routePeakDb[static_cast<size_t> (route)].store (-120.0f, std::memory_order_relaxed);",
    "for (int route = 0; route < count; ++route)\n        {\n            auto& peakCell = routePeakDb[static_cast<size_t> (route)];\n            const float oldPeak = peakCell.load (std::memory_order_relaxed);\n            peakCell.store (oldPeak + (-120.0f - oldPeak) * 0.008f, std::memory_order_relaxed);\n        }"
)

# Smooth peak, stereo position and width. Fast enough to follow a deliberate mix move, slow enough to read.
text = text.replace(
    "routePeakDb[routeArrayIndex].store (linearToDb (routePeak), std::memory_order_relaxed);\n            routeBalance[routeArrayIndex].store (balance, std::memory_order_relaxed);\n            routeWidth[routeArrayIndex].store (width, std::memory_order_relaxed);",
    "const float targetPeakDb = linearToDb (routePeak);\n            auto& peakCell = routePeakDb[routeArrayIndex];\n            const float oldPeakDb = peakCell.load (std::memory_order_relaxed);\n            const float peakAmount = targetPeakDb > oldPeakDb ? 0.18f : 0.020f;\n            peakCell.store (oldPeakDb + (targetPeakDb - oldPeakDb) * peakAmount, std::memory_order_relaxed);\n\n            auto& balanceCell = routeBalance[routeArrayIndex];\n            const float oldBalance = balanceCell.load (std::memory_order_relaxed);\n            balanceCell.store (oldBalance + (balance - oldBalance) * 0.035f, std::memory_order_relaxed);\n\n            auto& widthCell = routeWidth[routeArrayIndex];\n            const float oldWidth = widthCell.load (std::memory_order_relaxed);\n            widthCell.store (oldWidth + (width - oldWidth) * 0.035f, std::memory_order_relaxed);"
)

# Persistent spectral body: moderate attack and very slow release. This represents the sound's shape,
# not every FFT-sized fluctuation.
text = text.replace(
    "cell.store (old * 0.72f + normalized * 0.28f, std::memory_order_relaxed);",
    "const float amount = normalized > old ? 0.060f : 0.008f;\n            cell.store (old + (normalized - old) * amount, std::memory_order_relaxed);"
)

# Stable visual z-order: mixer order, not momentary loudness.
text = text.replace(
    "std::sort (active.begin (), active.end (), [] (const DrawTrack& a, const DrawTrack& b)\n        {\n            return a.peakDb < b.peakDb;\n        });",
    "std::sort (active.begin (), active.end (), [] (const DrawTrack& a, const DrawTrack& b)\n        {\n            if (!a.meta || !b.meta) return a.meta != nullptr;\n            return a.meta->mixerIndex < b.meta->mixerIndex;\n        });"
)

# Stable sidebar: exact FL mixer order. Never re-sort by live peak.
text = text.replace(
    "std::vector<DrawTrack> loudest = active;\n        std::sort (loudest.begin (), loudest.end (), [] (const DrawTrack& a, const DrawTrack& b)\n        {\n            return a.peakDb > b.peakDb;\n        });\n\n        SelectObject (dc, smallFont);\n        for (int i = 0; i < static_cast<int> (loudest.size ()) && i < maxRows; ++i)\n        {\n            const auto& track = loudest[static_cast<size_t> (i)];",
    "std::vector<DrawTrack> stableList = active;\n        std::sort (stableList.begin (), stableList.end (), [] (const DrawTrack& a, const DrawTrack& b)\n        {\n            if (!a.meta || !b.meta) return a.meta != nullptr;\n            return a.meta->mixerIndex < b.meta->mixerIndex;\n        });\n\n        SelectObject (dc, smallFont);\n        for (int i = 0; i < static_cast<int> (stableList.size ()) && i < maxRows; ++i)\n        {\n            const auto& track = stableList[static_cast<size_t> (i)];"
)

# Slightly lower activity threshold plus slow decay prevents tracks blinking in/out between notes.
text = text.replace("if (peak <= -72.0f)", "if (peak <= -78.0f)")
text = text.replace("ABOVE -72 dB", "ABOVE -78 dB")

# UI copy makes the changed intent explicit.
text = text.replace(
    "Live visual objects: frequency is vertical, stereo balance is horizontal, width changes object spread.",
    "Stable visual objects: mixer order is fixed; spectral shape, pan and width use perceptual smoothing."
)

out.write_text(text, encoding="utf-8")
print(out)
