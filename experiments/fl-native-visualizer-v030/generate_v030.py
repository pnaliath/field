from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v029 = root / "fl-native-visualizer-v029"

runpy.run_path(str(v029 / "generate_v029.py"), run_name="__main__")
src = v029 / "generated" / "fieldv029.cpp"
out = here / "generated" / "fieldv030.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.30 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.30 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.30 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


# Identity.
text = text.replace("Field V0.29", "Field V0.30")
text = text.replace("FieldV029", "FieldV030")
text = text.replace("V029", "V030")
text = text.replace("v029", "v030")
text = text.replace("FieldV029_diagnostics.csv", "FieldV030_diagnostics.csv")
text = text.replace("STABLE EQ DELTA", "WEB-SMOOTH GEOMETRY")

# -----------------------------------------------------------------------------
# Stable display profile. The raw 82nd-percentile learner is analysis state, not
# direct geometry. V0.29 exposed it after only two FFT observations, which made
# the first body enormous (often 28 Hz -> 18 kHz) and then visibly contract.
replace_once(
    "    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeLiveSpectrumDb;\n",
    "    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeLiveSpectrumDb;\n"
    "    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeDisplayProfileDb;\n"
    "    std::array<std::atomic<bool>, kMaxRoutes> routeDisplayProfileReady;\n"
    "    std::array<double, kMaxRoutes> routeContinuousSignalMs {};\n"
    "    std::array<std::atomic<bool>, kMaxRoutes> routeSustainedVisual;\n",
    "stable display profile state",
)

replace_once(
    "        for (auto& route : routeLiveSpectrumDb)\n"
    "            for (auto& band : route)\n"
    "                band.store (-120.0f, std::memory_order_relaxed);",
    "        for (auto& route : routeLiveSpectrumDb)\n"
    "            for (auto& band : route)\n"
    "                band.store (-120.0f, std::memory_order_relaxed);\n"
    "        for (auto& route : routeDisplayProfileDb)\n"
    "            for (auto& band : route)\n"
    "                band.store (-120.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : routeDisplayProfileReady) v.store (false, std::memory_order_relaxed);\n"
    "        for (auto& v : routeSustainedVisual) v.store (false, std::memory_order_relaxed);",
    "stable display profile init",
)

# Publish/latch geometry only after a real warm-up. After that, adapt very slowly.
# EQ readability is handled separately by the live delta overlay.
replace_once(
    "        routeProfileReady[routeIndex].store (\n"
    "            routeProfileFrames[routeIndex] >= static_cast<unsigned int> (kProfileMinFrames),\n"
    "            std::memory_order_relaxed);",
    "        routeProfileReady[routeIndex].store (\n"
    "            routeProfileFrames[routeIndex] >= static_cast<unsigned int> (kProfileMinFrames),\n"
    "            std::memory_order_relaxed);\n\n"
    "        constexpr unsigned int kDisplayWarmupFrames = 16u;\n"
    "        if (routeProfileFrames[routeIndex] >= kDisplayWarmupFrames)\n"
    "        {\n"
    "            const bool wasReady = routeDisplayProfileReady[routeIndex].load (std::memory_order_relaxed);\n"
    "            for (int band = 0; band < kBands; ++band)\n"
    "            {\n"
    "                auto& cell = routeDisplayProfileDb[routeIndex][static_cast<size_t> (band)];\n"
    "                const float targetDb = smoothDb[static_cast<size_t> (band)];\n"
    "                if (!wasReady)\n"
    "                    cell.store (targetDb, std::memory_order_relaxed);\n"
    "                else\n"
    "                {\n"
    "                    const float oldDb = cell.load (std::memory_order_relaxed);\n"
    "                    cell.store (oldDb + (targetDb - oldDb) * 0.012f, std::memory_order_relaxed);\n"
    "                }\n"
    "            }\n"
    "            routeDisplayProfileReady[routeIndex].store (true, std::memory_order_release);\n"
    "        }",
    "display profile warmup and slow adaptation",
)

# Geometry occupancy reads the stable display profile instead of the continuously
# changing learner. Limit replacement to the learnedShapeEnergy function body.
start = text.find("    float learnedShapeEnergy (size_t routeIndex, int band) const")
end = text.find("    struct ProjectedPoint", start)
if start < 0 or end < 0:
    raise RuntimeError("V0.30 could not isolate learnedShapeEnergy")
block = text[start:end]
block = block.replace("routeProfileReady[routeIndex]", "routeDisplayProfileReady[routeIndex]")
block = block.replace("routeProfileDb[routeIndex]", "routeDisplayProfileDb[routeIndex]")
text = text[:start] + block + text[end:]

# Renderer must wait for the stable body, not the raw two-frame profile.
text = text.replace(
    "        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))\n            return;",
    "        if (!routeDisplayProfileReady[routeIndex].load (std::memory_order_acquire))\n            return;",
    1,
)

# V0.29 EQ baseline must be the same stable geometry the user sees.
text = text.replace(
    "const float learnedDb = routeProfileDb[routeIndex][static_cast<size_t> (i)].load (",
    "const float learnedDb = routeDisplayProfileDb[routeIndex][static_cast<size_t> (i)].load (",
    1,
)

# -----------------------------------------------------------------------------
# Learn sustained-vs-transient behavior. Once a route has produced >180 ms of
# continuous signal, treat it as a sustained object for the session. This keeps
# vocal/guitar/pads from spawning a new visual body on every detected syllable or
# attack. A genuine learned L/R split still forces transient current-hit rendering.
replace_once(
    "            const bool hasSignal = targetPeakDb > -114.0f;\n",
    "            const bool hasSignal = targetPeakDb > -114.0f;\n"
    "            const float visualBlockMs = std::max (0.1f, diagBlockMs.load (std::memory_order_relaxed));\n"
    "            if (hasSignal)\n"
    "            {\n"
    "                routeContinuousSignalMs[routeArrayIndex] += static_cast<double> (visualBlockMs);\n"
    "                if (routeContinuousSignalMs[routeArrayIndex] >= 180.0)\n"
    "                    routeSustainedVisual[routeArrayIndex].store (true, std::memory_order_release);\n"
    "            }\n"
    "            else\n"
    "                routeContinuousSignalMs[routeArrayIndex] = 0.0;\n",
    "sustained visual classification",
)

# In event expansion, sustained mono sources bypass snapshots entirely. Their
# stable geometry remains one object and only its smoothed presence changes.
replace_once(
    "            const float stableWidth = routeProfileReady[idx].load (std::memory_order_relaxed)\n"
    "                ? learnedWidth : liveWidth;",
    "            const float stableWidth = routeDisplayProfileReady[idx].load (std::memory_order_acquire)\n"
    "                ? learnedWidth : liveWidth;\n"
    "            const bool transientVisual = voices >= 2 ||\n"
    "                !routeSustainedVisual[idx].load (std::memory_order_acquire);\n"
    "            if (!transientVisual)\n"
    "            {\n"
    "                DrawTrack d = sourceTrack;\n"
    "                d.spatialVoiceIndex = 0;\n"
    "                d.spatialVoiceCount = 1;\n"
    "                d.balance = std::clamp (livePan * xAxisSensitivity, -1.0f, 1.0f);\n"
    "                d.width = stableWidth;\n"
    "                spatialActive.push_back (d);\n"
    "                continue;\n"
    "            }",
    "sustained sources bypass event snapshots",
)

# -----------------------------------------------------------------------------
# Presence should feel like one smooth web object, not flash with every small gap.
text = text.replace("std::exp (-blockMs / 260.0f)", "std::exp (-blockMs / 360.0f)", 1)
text = text.replace("targetPresence > oldPresence ? 0.52f : 0.018f", "targetPresence > oldPresence ? 0.24f : 0.010f", 1)

# Remove the decorative grey specular ellipse. It was never audio data and is
# visually confusing in an analysis surface.
text = text.replace(
    "            if (presence > 0.10f && x1 > x0 + 8 && y1 > y0 + 8)\n            {",
    "            if (false && presence > 0.10f && x1 > x0 + 8 && y1 > y0 + 8)\n            {",
    1,
)

text = text.replace(
    "V0.29 stable EQ: level-normalized + temporal/coherent delta + badge hysteresis",
    "V0.30 web-smooth: warm stable geometry + sustained-body mode + smooth presence"
)

out.write_text(text, encoding="utf-8")
print(out)
