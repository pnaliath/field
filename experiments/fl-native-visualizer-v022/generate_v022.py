from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v021 = root / "fl-native-visualizer-v021"

# Start from compile-green V0.21 spatial-voice build.
runpy.run_path(str(v021 / "generate_v021.py"), run_name="__main__")
src = v021 / "generated" / "fieldv021.cpp"
out = here / "generated" / "fieldv022.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.22 could not find patch point: {label}")
    text = text.replace(old, new, 1)

# Fresh identity / diagnostic log.
text = text.replace("Field V0.21", "Field V0.22")
text = text.replace("FieldV021", "FieldV022")
text = text.replace("V021", "V022")
text = text.replace("v021", "v022")
text = text.replace("FieldV021_diagnostics.csv", "FieldV022_diagnostics.csv")
text = text.replace("WEB SPATIAL VOICES", "STABLE ROOM + STEREO")

# -----------------------------------------------------------------------------
# 1) Stable spatial voices: never three bodies, and never let an already accepted
# split collapse/recluster every few hits. This directly addresses V0.21 clutter.
replace_once(
    "    void recomputeSpatialVoices (size_t routeIndex)\n"
    "    {\n"
    "        if (routeIndex >= kMaxRoutes)\n"
    "            return;\n"
    "        const int n = std::clamp (spatialEventCount[routeIndex], 0, kSpatialEventHistory);",
    "    void recomputeSpatialVoices (size_t routeIndex)\n"
    "    {\n"
    "        if (routeIndex >= kMaxRoutes)\n"
    "            return;\n"
    "        // Once a genuine L/R split is accepted, keep it stable for the session.\n"
    "        // This removes 1->2->3->1 topology flicker measured in V0.21.\n"
    "        if (spatialVoiceCount[routeIndex].load (std::memory_order_acquire) >= 2)\n"
    "            return;\n"
    "        const int n = std::clamp (spatialEventCount[routeIndex], 0, kSpatialEventHistory);",
    "lock accepted stereo split",
)

# Require a meaningful observation history before splitting.
text = text.replace("        if (n < 4)\n", "        if (n < 10)\n", 1)
# Stronger evidence than the browser offline analyser because streaming estimates are noisier.
text = text.replace("        if (sd < 0.07f)\n", "        if (sd < 0.11f)\n", 1)
# V0.22 is deliberately at most L/R: no third centre/body.
text = text.replace("        for (int kTry : {3, 2})\n", "        for (int kTry : {2})\n", 1)
# Wider, better-balanced split threshold avoids false guitar/pad splits.
text = text.replace(" < 0.16f)\n                    accepted = false;", " < 0.28f)\n                    accepted = false;", 1)
text = text.replace(" < 0.12f)\n                    accepted = false;", " < 0.22f)\n                    accepted = false;", 1)

# -----------------------------------------------------------------------------
# 2) Presence: smoother persistence across short gaps. Geometry remains static;
# only opacity/presence is smoothed. Pause still fades fully, just less twitchily.
text = text.replace("std::exp (-blockMs / 145.0f)", "std::exp (-blockMs / 260.0f)", 1)
text = text.replace("routePresenceHoldBlocks[routeArrayIndex] = 18;", "routePresenceHoldBlocks[routeArrayIndex] = 24;", 1)
text = text.replace("targetPresence > oldPresence ? 0.46f : 0.045f", "targetPresence > oldPresence ? 0.52f : 0.018f", 1)

# -----------------------------------------------------------------------------
# 3) Recalibrate absolute Z. V0.21 diagnostics had 7/13 sources at z=.84-.88.
# Keep depth independent per track, but use only the useful front/mid ~60% of room.
# Extremely low/incorrect learned loudness therefore cannot pin bodies to back wall.
text = text.replace(
    "const float backness = clamp01 ((-10.0f - loudDb) / 45.0f);",
    "const float backness = clamp01 ((-18.0f - loudDb) / 62.0f);"
)
replace_once(
    "            const float targetDepth = 0.14f + backness * 0.74f;",
    "            const float targetDepth = 0.10f + backness * 0.50f;",
    "forward depth calibration",
)
replace_once(
    "            track.visualZ = std::clamp (smoothDepth, 0.12f, 0.90f);",
    "            track.visualZ = std::clamp (smoothDepth, 0.08f, 0.62f);",
    "forward depth clamp",
)
text = text.replace("                track.visualZ = 0.52f;", "                track.visualZ = 0.38f;", 1)

# Diagnostics banner.
text = text.replace(
    "V0.21 spatial: browser body width + onset-position voices",
    "V0.22 stable room: max 2 locked voices + smoother presence + forward Z"
)

out.write_text(text, encoding="utf-8")
print(out)
