from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v030 = root / "fl-native-visualizer-v030"

runpy.run_path(str(v030 / "generate_v030.py"), run_name="__main__")
src = v030 / "generated" / "fieldv030.cpp"
out = here / "generated" / "fieldv031.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.31 could not find patch point: {label}")
    text = text.replace(old, new, 1)


# Identity.
text = text.replace("Field V0.30", "Field V0.31")
text = text.replace("FieldV030", "FieldV031")
text = text.replace("V030", "V031")
text = text.replace("v030", "v031")
text = text.replace("FieldV030_diagnostics.csv", "FieldV031_diagnostics.csv")
text = text.replace("WEB-SMOOTH GEOMETRY", "STABLE DUAL VOICES")

# -----------------------------------------------------------------------------
# V0.30 correctly learned a two-voice GUITAR CHORDS topology, but its sustained
# bypass collapsed the render to one raw live-pan body. Keep a UI-side common
# shift for sustained split pairs so the learned L/R centres remain intact and
# move together without chasing every per-block balance fluctuation.
replace_once(
    "    std::array<std::atomic<bool>, kMaxRoutes> routeSustainedVisual;\n",
    "    std::array<std::atomic<bool>, kMaxRoutes> routeSustainedVisual;\n"
    "    std::array<float, kMaxRoutes> routeStablePairShift {};\n"
    "    std::array<unsigned long long, kMaxRoutes> routeStablePairShiftLastMs {};\n",
    "stable pair shift state",
)

old_sustained_block = r'''            const bool transientVisual = voices >= 2 ||
                !routeSustainedVisual[idx].load (std::memory_order_acquire);
            if (!transientVisual)
            {
                DrawTrack d = sourceTrack;
                d.spatialVoiceIndex = 0;
                d.spatialVoiceCount = 1;
                d.balance = std::clamp (livePan * xAxisSensitivity, -1.0f, 1.0f);
                d.width = stableWidth;
                spatialActive.push_back (d);
                continue;
            }'''

new_sustained_block = r'''            const bool sustainedVisual = routeSustainedVisual[idx].load (std::memory_order_acquire);
            if (sustainedVisual)
            {
                if (voices >= 2)
                {
                    // Sustained discrete L/R material is TWO stable bodies. V0.30
                    // incorrectly collapsed this to one current-pan body. Preserve
                    // the learned centres and apply only a shared, smoothed offset.
                    const float targetShift = std::clamp (
                        routeSpatialPanShift[idx].load (std::memory_order_relaxed), -0.85f, 0.85f);
                    const unsigned long long pairNow = GetTickCount64 ();
                    auto& lastPairMs = routeStablePairShiftLastMs[idx];
                    auto& pairShift = routeStablePairShift[idx];
                    if (lastPairMs == 0ull)
                    {
                        pairShift = targetShift;
                        lastPairMs = pairNow;
                    }
                    else if (pairNow > lastPairMs)
                    {
                        const float dtMs = static_cast<float> (
                            std::min<unsigned long long> (80ull, pairNow - lastPairMs));
                        const float alpha = 1.0f - std::exp (-dtMs / 180.0f);
                        pairShift += (targetShift - pairShift) * alpha;
                        lastPairMs = pairNow;
                    }

                    for (int voice = 0; voice < 2; ++voice)
                    {
                        DrawTrack d = sourceTrack;
                        d.spatialVoiceIndex = voice;
                        d.spatialVoiceCount = 2;
                        d.renderLabel = voice == 0;
                        d.renderFxAura = voice == 0;
                        const float learnedCentre = spatialVoicePan[idx][static_cast<size_t> (voice)].load (
                            std::memory_order_relaxed);
                        d.balance = std::clamp ((learnedCentre + pairShift) * xAxisSensitivity,
                            -1.0f, 1.0f);
                        d.width = stableWidth;
                        spatialActive.push_back (d);
                    }
                    continue;
                }

                // Sustained single-position / continuous-stereo source: one body.
                DrawTrack d = sourceTrack;
                d.spatialVoiceIndex = 0;
                d.spatialVoiceCount = 1;
                d.balance = std::clamp (livePan * xAxisSensitivity, -1.0f, 1.0f);
                d.width = stableWidth;
                spatialActive.push_back (d);
                continue;
            }

            // Non-sustained routes keep V0.25/V0.30 event snapshots. A learned
            // L/R transient such as alternating hats therefore still shows only
            // the currently sounding side, never two permanent anchors.'''

replace_once(old_sustained_block, new_sustained_block, "restore sustained two-voice topology")

text = text.replace(
    "V0.30 web-smooth: warm stable geometry + sustained-body mode + smooth presence",
    "V0.31: sustained discrete L/R stays two stable bodies; transient L/R stays current-hit only"
)

out.write_text(text, encoding="utf-8")
print(out)
