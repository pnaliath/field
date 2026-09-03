from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v007_dir = root / "fl-native-visualizer-v007"

runpy.run_path(str(v007_dir / "generate_v007.py"), run_name="__main__")
src = v007_dir / "generated" / "fieldv007.cpp"
out = here / "generated" / "fieldv008.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.08 could not find patch point: {label}")
    text = text.replace(old, new, 1)

# Fresh FL-native identity.
text = text.replace("Field V0.07 FX Aware Visualizer", "Field V0.08 Sticky FX Visualizer")
text = text.replace("FieldV007", "FieldV008")
text = text.replace("V0.07", "V0.08")
text = text.replace("V007", "V008")

# Learn real audio-bearing routes at a much lower floor. This latch is only for existence,
# never for moment-to-moment visibility.
text = text.replace("if (targetPeakDb > -88.0f)", "if (targetPeakDb > -96.0f)")

# Preserve the previous FX association before each classifier pass. A return that was already
# confidently identified must not become a primary object merely because the wet send gets louder
# or the instantaneous correlation changes.
replace_once(
    "    void classifyTemporalFx ()\n    {\n        fxLinks.clear ();",
    "    void classifyTemporalFx ()\n    {\n        const auto previousFxLinks = fxLinks;\n        fxLinks.clear ();",
    "preserve previous FX links",
)

replace_once(
    "                fxLinks.push_back (link);\n            }\n        }\n    }\n\n    bool isFxReturnRoute",
    "                fxLinks.push_back (link);\n            }\n        }\n\n"
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
    "        }\n"
    "    }\n\n    bool isFxReturnRoute",
    "sticky FX hysteresis",
)

# Primary objects are session-persistent once a route has ever carried meaningful audio.
# Instantaneous -78 dB no longer decides whether an object exists.
replace_once(
    "            const float peak = routePeakDb[idx].load (std::memory_order_relaxed);\n"
    "            if (peak <= -78.0f)\n"
    "                continue;\n"
    "            if (isFxReturnRoute (item.routeIndex))",
    "            const float peak = routePeakDb[idx].load (std::memory_order_relaxed);\n"
    "            if (!everActive[idx].load (std::memory_order_relaxed))\n"
    "                continue;\n"
    "            if (isFxReturnRoute (item.routeIndex))",
    "persistent primary objects",
)

# Remove the misleading instantaneous dB-state message.
text = text.replace(
    'L"FIELD IS RUNNING, BUT NO ROUTED BUFFER IS CURRENTLY ABOVE -78 dB."',
    'L"FIELD IS RUNNING. WAITING TO LEARN THE FIRST PRIMARY AUDIO-BEARING TRACK."'
)

# Make the intent explicit in the subtitle when the inherited UI string is present.
text = text.replace(
    "Persistent mixer-order list. Temporal FX returns are attached to their likely source objects as faded ambience/echo layers.",
    "Persistent objects do not disappear on quiet passages. Learned FX-return identity stays stable across send-level changes."
)

out.write_text(text, encoding="utf-8")
print(out)
