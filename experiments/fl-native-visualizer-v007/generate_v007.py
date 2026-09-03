from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v006_dir = root / "fl-native-visualizer-v006"

runpy.run_path(str(v006_dir / "generate_v006_fixed3.py"), run_name="__main__")
src = v006_dir / "generated" / "fieldv006.cpp"
out = here / "generated" / "fieldv007.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.07 could not find patch point: {label}")
    text = text.replace(old, new, 1)

text = text.replace("Field V0.06 FX Aware Visualizer", "Field V0.07 FX Aware Visualizer")
text = text.replace("FieldV006", "FieldV007")
text = text.replace("V0.06", "V0.07")
text = text.replace("V006", "V007")

text = text.replace("constexpr int kHistoryFrames = 160;", "constexpr int kHistoryFrames = 256;")
text = text.replace(
    "constexpr std::array<int, 11> kFxLags {2, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128};",
    "constexpr std::array<int, 15> kFxLags {1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192};"
)

replace_once(
    '        if (has ("delay") || has ("echo") || has ("slap"))\n            return 2;\n        if (has ("reverb") || has ("verb") || has ("room") || has ("hall") || has ("plate"))\n            return 1;',
    '        if (has ("delay") || has ("echo") || has ("slap") || s == "del" || s == "dly")\n            return 2;\n        if (has ("reverb") || has ("verb") || has ("room") || has ("hall") || has ("plate") || s == "rev" || s == "rvb")\n            return 1;',
    "short FX aliases"
)

spectral_method = r'''
    float spectralSimilarity (size_t sourceIndex, size_t returnIndex) const
    {
        if (sourceIndex >= kMaxRoutes || returnIndex >= kMaxRoutes)
            return 0.0f;
        double dot = 0.0, aa = 0.0, bb = 0.0;
        for (int band = 0; band < kBands; ++band)
        {
            const double a = std::sqrt (std::max (0.0f,
                routeSpectrum[sourceIndex][static_cast<size_t> (band)].load (std::memory_order_relaxed)));
            const double b = std::sqrt (std::max (0.0f,
                routeSpectrum[returnIndex][static_cast<size_t> (band)].load (std::memory_order_relaxed)));
            dot += a * b; aa += a * a; bb += b * b;
        }
        const double denom = std::sqrt (aa * bb);
        if (denom < 1.0e-8)
            return 0.0f;
        return static_cast<float> (std::clamp (dot / denom, 0.0, 1.0));
    }

'''
replace_once("    void classifyTemporalFx ()\n    {", spectral_method + "    void classifyTemporalFx ()\n    {", "spectral similarity method")
replace_once("            float tail = 0.0f;\n        };", "            float tail = 0.0f;\n            float spectral = 0.0f;\n        };", "candidate spectral field")

replace_once(
    "                const float tail = tailRatio (s, r, bestLag, available, writes);\n                const float lagAdvantage = best - zero;\n                const float widthDelta = std::max (0.0f,\n                    returnWidthNow - routeWidth[s].load (std::memory_order_relaxed));\n                const float hintBoost = nameHint == 0 ? 0.0f : (nameHint == 3 ? 0.035f : 0.075f);\n\n                const float score =\n                    best * 0.56f +\n                    tail * 0.22f +\n                    clamp01 ((lagAdvantage + 0.05f) * 2.2f) * 0.13f +\n                    clamp01 (widthDelta * 2.5f) * 0.09f +\n                    hintBoost;\n\n                const bool temporal = best > 0.40f &&\n                    (lagAdvantage > 0.035f || tail > 0.22f || (nameHint != 0 && tail > 0.12f));\n                if (!temporal || score < 0.46f)\n                    continue;\n\n                candidates.push_back ({sourceRoute, bestLag, score, best, zero, tail});",
    "                const float tail = tailRatio (s, r, bestLag, available, writes);\n                const float spectral = spectralSimilarity (s, r);\n                const float lagAdvantage = best - zero;\n                const float widthDelta = std::max (0.0f,\n                    returnWidthNow - routeWidth[s].load (std::memory_order_relaxed));\n                const float hintBoost = nameHint == 0 ? 0.0f : (nameHint == 3 ? 0.035f : 0.085f);\n\n                const float score =\n                    clamp01 ((best + 0.05f) / 0.85f) * 0.30f +\n                    tail * 0.24f +\n                    spectral * 0.24f +\n                    clamp01 ((lagAdvantage + 0.03f) * 2.8f) * 0.11f +\n                    clamp01 (widthDelta * 2.8f) * 0.07f +\n                    hintBoost;\n\n                const bool laggedEvidence = best > 0.25f && lagAdvantage > 0.025f &&\n                    (tail > 0.075f || spectral > 0.50f);\n                const bool diffuseEvidence = tail > 0.15f && spectral > 0.43f &&\n                    (widthDelta > 0.035f || best > 0.28f);\n                const bool hintedEvidence = nameHint != 0 && spectral > 0.28f &&\n                    (tail > 0.055f || best > 0.18f);\n                const bool temporal = laggedEvidence || diffuseEvidence || hintedEvidence;\n                if (!temporal || score < 0.37f)\n                    continue;\n\n                candidates.push_back ({sourceRoute, bestLag, score, best, zero, tail, spectral});",
    "stronger FX evidence"
)

text = text.replace("            if (top < 0.50f)\n                continue;", "            if (top < 0.40f)\n                continue;")
text = text.replace("                if (accepted >= 4 || c.score < std::max (0.46f, top * 0.72f))", "                if (accepted >= 4 || c.score < std::max (0.36f, top * 0.68f))")
text = text.replace("                bool delayLike = (c.delayedCorr > 0.62f && (c.delayedCorr - c.zeroCorr) > 0.09f && c.tail < 0.62f);", "                bool delayLike = (c.delayedCorr > 0.52f && (c.delayedCorr - c.zeroCorr) > 0.065f && c.tail < 0.58f);")
text = text.replace("if (reverbAmount > 0.01f)", "if (reverbAmount > 0.004f)")
text = text.replace("if (delayAmount > 0.01f)", "if (delayAmount > 0.004f)")

out.write_text(text, encoding="utf-8")
print(out)
