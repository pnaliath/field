from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v008_dir = root / "fl-native-visualizer-v008"

runpy.run_path(str(v008_dir / "generate_v008.py"), run_name="__main__")
src = v008_dir / "generated" / "fieldv008.cpp"
out = here / "generated" / "fieldv009.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.09 could not find patch point: {label}")
    text = text.replace(old, new, 1)

# Fresh FL-native identity.
text = text.replace("Field V0.08 Sticky FX Visualizer", "Field V0.09 Recovering FX Visualizer")
text = text.replace("FieldV008", "FieldV009")
text = text.replace("V0.08", "V0.09")
text = text.replace("V008", "V009")

# V0.08's indefinite sticky retention is replaced by a confidence/hysteresis state.
# Keep previous links only as a short-term source association cache while a latched return
# temporarily loses measurable correlation.
replace_once(
    "        // Sticky FX identity / hysteresis. If a previously classified return is not\n"
    "        // confidently reclassified on this pass, retain its last source association.\n"
    "        // Send-level changes therefore change aura intensity, not object identity.\n"
    "        for (const auto& previous : previousFxLinks)\n"
    "        {\n"
    "            bool returnAlreadyPresent = false;\n"
    "            for (const auto& current : fxLinks)\n"
    "            {\n"
    "                if (current.returnRoute == previous.returnRoute)\n"
    "                {\n"
    "                    returnAlreadyPresent = true;\n"
    "                    break;\n"
    "                }\n"
    "            }\n"
    "            if (returnAlreadyPresent)\n"
    "                continue;\n"
    "            if (previous.returnRoute < 1 || previous.returnRoute > count)\n"
    "                continue;\n"
    "            const size_t returnIndex = static_cast<size_t> (previous.returnRoute - 1);\n"
    "            if (!everActive[returnIndex].load (std::memory_order_relaxed))\n"
    "                continue;\n"
    "            FxLink held = previous;\n"
    "            const float currentPeak = routePeakDb[returnIndex].load (std::memory_order_relaxed);\n"
    "            const float levelDrivenWet = clamp01 ((currentPeak + 72.0f) / 54.0f);\n"
    "            held.wetAmount = clamp01 (std::max (previous.wetAmount * 0.985f, levelDrivenWet));\n"
    "            held.score = std::max (previous.score * 0.995f, 0.40f);\n"
    "            fxLinks.push_back (held);\n"
    "        }",
    "        // Confidence + hysteresis. A return must be supported repeatedly before it is\n"
    "        // hidden as an FX return. False positives recover; silence itself does not\n"
    "        // erase a learned return.\n"
    "        std::array<float, kMaxRoutes> bestProposalScore {};\n"
    "        std::array<bool, kMaxRoutes> hasProposal {};\n"
    "        for (const auto& link : fxLinks)\n"
    "        {\n"
    "            if (link.returnRoute < 1 || link.returnRoute > count)\n"
    "                continue;\n"
    "            const size_t idx = static_cast<size_t> (link.returnRoute - 1);\n"
    "            hasProposal[idx] = true;\n"
    "            bestProposalScore[idx] = std::max (bestProposalScore[idx], link.score);\n"
    "        }\n\n"
    "        for (int route = 1; route <= count; ++route)\n"
    "        {\n"
    "            const size_t idx = static_cast<size_t> (route - 1);\n"
    "            float confidence = fxReturnConfidence[idx];\n"
    "            if (hasProposal[idx])\n"
    "            {\n"
    "                const float evidence = clamp01 ((bestProposalScore[idx] - 0.34f) / 0.46f);\n"
    "                confidence = clamp01 (confidence + 0.11f + evidence * 0.10f);\n"
    "                fxReturnMisses[idx] = 0;\n"
    "                if (!fxReturnLatched[idx] && confidence >= 0.70f)\n"
    "                    fxReturnLatched[idx] = true;\n"
    "            }\n"
    "            else if (fxReturnLatched[idx])\n"
    "            {\n"
    "                const float currentPeak = routePeakDb[idx].load (std::memory_order_relaxed);\n"
    "                // Do not punish a return just because the source/return is silent. Only\n"
    "                // active contradictory audio slowly erodes the FX identity. Name hints\n"
    "                // slow that erosion but never make it permanent.\n"
    "                if (currentPeak > -76.0f)\n"
    "                {\n"
    "                    const float decay = temporalNameHint (route) != 0 ? 0.004f : 0.012f;\n"
    "                    confidence = std::max (0.0f, confidence - decay);\n"
    "                    ++fxReturnMisses[idx];\n"
    "                }\n"
    "                if (confidence < 0.30f && fxReturnMisses[idx] > 20)\n"
    "                {\n"
    "                    fxReturnLatched[idx] = false;\n"
    "                    fxReturnMisses[idx] = 0;\n"
    "                }\n"
    "            }\n"
    "            else\n"
    "            {\n"
    "                confidence = std::max (0.0f, confidence - 0.08f);\n"
    "                fxReturnMisses[idx] = 0;\n"
    "            }\n"
    "            fxReturnConfidence[idx] = confidence;\n"
    "        }\n\n"
    "        // If a latched return has a brief ambiguous classifier pass, retain its previous\n"
    "        // source link so the halo does not jump/disappear. This cache is bounded by the\n"
    "        // confidence state above rather than being permanent as in V0.08.\n"
    "        for (const auto& previous : previousFxLinks)\n"
    "        {\n"
    "            if (previous.returnRoute < 1 || previous.returnRoute > count)\n"
    "                continue;\n"
    "            const size_t idx = static_cast<size_t> (previous.returnRoute - 1);\n"
    "            if (!fxReturnLatched[idx] || hasProposal[idx])\n"
    "                continue;\n"
    "            FxLink held = previous;\n"
    "            const float currentPeak = routePeakDb[idx].load (std::memory_order_relaxed);\n"
    "            const float levelDrivenWet = clamp01 ((currentPeak + 72.0f) / 54.0f);\n"
    "            held.wetAmount = clamp01 (std::max (previous.wetAmount * 0.97f, levelDrivenWet));\n"
    "            held.score = std::max (0.20f, previous.score * 0.985f);\n"
    "            fxLinks.push_back (held);\n"
    "        }",
    "replace indefinite sticky latch",
)

# FX-return visibility now comes from the hysteresis state, not simply from one classifier pass.
replace_once(
    "    bool isFxReturnRoute (int route) const\n"
    "    {\n"
    "        for (const auto& link : fxLinks)\n"
    "            if (link.returnRoute == route)\n"
    "                return true;\n"
    "        return false;\n"
    "    }",
    "    bool isFxReturnRoute (int route) const\n"
    "    {\n"
    "        if (route < 1 || route > kMaxRoutes)\n"
    "            return false;\n"
    "        return fxReturnLatched[static_cast<size_t> (route - 1)];\n"
    "    }",
    "FX return hysteresis lookup",
)

# Safety path: even if classification is temporarily wrong, never allow the whole visual field
# to disappear while real audio-bearing routes are known. Render the least-FX-like learned route.
replace_once(
    "        std::sort (active.begin (), active.end (), [] (const DrawTrack& a, const DrawTrack& b)\n",
    "        if (active.empty ())\n"
    "        {\n"
    "            const InputMetadata* fallback = nullptr;\n"
    "            float bestPenalty = 1000.0f;\n"
    "            for (const auto& item : inputs)\n"
    "            {\n"
    "                if (item.routeIndex < 1 || item.routeIndex > kMaxRoutes)\n"
    "                    continue;\n"
    "                const size_t idx = static_cast<size_t> (item.routeIndex - 1);\n"
    "                if (!everActive[idx].load (std::memory_order_relaxed))\n"
    "                    continue;\n"
    "                float penalty = fxReturnConfidence[idx];\n"
    "                if (temporalNameHint (item.routeIndex) != 0)\n"
    "                    penalty += 0.35f;\n"
    "                if (penalty < bestPenalty)\n"
    "                {\n"
    "                    bestPenalty = penalty;\n"
    "                    fallback = &item;\n"
    "                }\n"
    "            }\n"
    "            if (fallback)\n"
    "            {\n"
    "                const size_t idx = static_cast<size_t> (fallback->routeIndex - 1);\n"
    "                DrawTrack d;\n"
    "                d.meta = fallback;\n"
    "                d.peakDb = routePeakDb[idx].load (std::memory_order_relaxed);\n"
    "                d.balance = routeBalance[idx].load (std::memory_order_relaxed);\n"
    "                d.width = routeWidth[idx].load (std::memory_order_relaxed);\n"
    "                active.push_back (d);\n"
    "            }\n"
    "        }\n\n"
    "        std::sort (active.begin (), active.end (), [] (const DrawTrack& a, const DrawTrack& b)\n",
    "non-empty primary safety path",
)

# Add classifier confidence state members.
replace_once(
    "    std::vector<FxLink> fxLinks;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeBalance;",
    "    std::vector<FxLink> fxLinks;\n"
    "    std::array<float, kMaxRoutes> fxReturnConfidence {};\n"
    "    std::array<bool, kMaxRoutes> fxReturnLatched {};\n"
    "    std::array<int, kMaxRoutes> fxReturnMisses {};\n"
    "    std::array<std::atomic<float>, kMaxRoutes> routeBalance;",
    "FX confidence members",
)

# Better diagnostic copy; no threshold language.
text = text.replace(
    "Persistent objects do not disappear on quiet passages. Learned FX-return identity stays stable across send-level changes.",
    "Persistent objects stay visible. FX returns use confidence + hysteresis, so false positives can recover without send-level flicker."
)
text = text.replace(
    'L"FIELD IS RUNNING. WAITING TO LEARN THE FIRST PRIMARY AUDIO-BEARING TRACK."',
    'L"FIELD IS ANALYSING ROUTED AUDIO. PRIMARY OBJECTS WILL STAY VISIBLE ONCE LEARNED."'
)

out.write_text(text, encoding="utf-8")
print(out)
