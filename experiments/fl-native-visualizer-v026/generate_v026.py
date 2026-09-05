from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v025 = root / "fl-native-visualizer-v025"

# Start from compile-green V0.25 event-snapshot build.
runpy.run_path(str(v025 / "generate_v025_fixed.py"), run_name="__main__")
src = v025 / "generated" / "fieldv025.cpp"
out = here / "generated" / "fieldv026.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.26 could not find patch point: {label}")
    text = text.replace(old, new, 1)


def replace_between(start: str, end: str, replacement: str, label: str) -> None:
    global text
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"V0.26 could not find start marker: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"V0.26 could not find end marker: {label}")
    text = text[:a] + replacement + text[b:]


# Identity.
text = text.replace("Field V0.25", "Field V0.26")
text = text.replace("FieldV025", "FieldV026")
text = text.replace("V025", "V026")
text = text.replace("v025", "v026")
text = text.replace("FieldV025_diagnostics.csv", "FieldV026_diagnostics.csv")
text = text.replace("EVENT SNAPSHOTS", "FROZEN HIT TAILS")

# Latest calibrated values selected by the user.
text = text.replace("float xAxisSensitivity = 1.25f;", "float xAxisSensitivity = 0.95f;", 1)
text = text.replace("float zAxisSensitivity = 1.70f;", "float zAxisSensitivity = 1.20f;", 1)

# The newest event must not visually fall below the route's own release envelope
# before its snapshot lifetime ends. Older coexisting level snapshots still use
# their independent event fade, so a newer hit does not relight old positions.
replace_once(
    "                    const float fade = ageMs <= 90.0f ? 1.0f :\n"
    "                        clamp01 (1.0f - (ageMs - 90.0f) / 350.0f);\n"
    "                    if (fade <= 0.01f)",
    "                    const float eventFade = ageMs <= 90.0f ? 1.0f :\n"
    "                        clamp01 (1.0f - (ageMs - 90.0f) / 350.0f);\n"
    "                    const float routeTailPresence = clamp01 (routeVisualPresence[idx].load (\n"
    "                        std::memory_order_relaxed));\n"
    "                    const float fade = ev.slot == newestSlot\n"
    "                        ? std::max (eventFade, routeTailPresence)\n"
    "                        : eventFade;\n"
    "                    if (fade <= 0.01f)",
    "newest snapshot follows tail opacity without moving",
)

# V0.25 expired the event snapshot at ~440 ms and then resurrected a normal body.
# If the hit had already ended, that normal body inherited the route's changing depth
# estimator and visibly travelled backward before disappearing. V0.26 only falls
# back to the live sustained body when there is CURRENT real signal. Otherwise the
# latest event position is reconstructed and fades at its immutable X/Z coordinates.
frozen_tail = r'''            // No recent event snapshot. If audio is still genuinely present,
            // this is a sustained source and may use the live body. If the hit has ended,
            // NEVER resurrect the live depth body: fade the last event in place.
            const bool hasCurrentSignal = routeHasSignal[idx].load (std::memory_order_relaxed);
            if (!hasCurrentSignal)
            {
                unsigned long long latestBorn = 0ull;
                float latestPan = livePan;
                float latestLevelDb = -120.0f;
                for (int s = 0; s < kVisualEventSlots; ++s)
                {
                    const auto born = visualEventBornMs[idx][static_cast<size_t> (s)].load (
                        std::memory_order_acquire);
                    if (born > latestBorn)
                    {
                        latestBorn = born;
                        latestPan = visualEventPan[idx][static_cast<size_t> (s)].load (
                            std::memory_order_relaxed);
                        latestLevelDb = visualEventLevelDb[idx][static_cast<size_t> (s)].load (
                            std::memory_order_relaxed);
                    }
                }

                const float tailPresence = clamp01 (routeVisualPresence[idx].load (
                    std::memory_order_relaxed));
                if (latestBorn != 0ull && tailPresence > 0.010f)
                {
                    DrawTrack d = sourceTrack;
                    d.eventSnapshot = true;
                    d.visualPresenceOverride = tailPresence;
                    d.renderLabel = true;
                    d.renderFxAura = true;
                    d.spatialVoiceIndex = 0;
                    d.spatialVoiceCount = voices >= 2 ? 2 : 1;
                    d.balance = std::clamp (latestPan * xAxisSensitivity, -1.0f, 1.0f);
                    d.width = liveWidth;

                    const float backness = clamp01 ((-14.0f - latestLevelDb) / 58.0f);
                    const float baseDepth = 0.10f + backness * 0.72f;
                    d.visualZ = std::clamp (
                        0.46f + (baseDepth - 0.46f) * zAxisSensitivity, 0.08f, 0.84f);
                    const float frontness = 1.0f - backness;
                    d.volumeThickness = 0.040f + frontness * 0.075f;
                    spatialActive.push_back (d);
                }
                continue;
            }

            // A genuinely sustained source is still sounding: use one current live body.
            DrawTrack d = sourceTrack;
            d.spatialVoiceIndex = 0;
            d.spatialVoiceCount = voices >= 2 ? 2 : 1;
            d.balance = std::clamp (livePan * xAxisSensitivity, -1.0f, 1.0f);
            d.width = liveWidth;
            spatialActive.push_back (d);
'''
replace_between(
    "            // No recent hit: never resurrect both learned L/R anchors.",
    "        }\n        active = std::move (spatialActive);",
    frozen_tail,
    "freeze ended-hit position through tail fade",
)

text = text.replace(
    "V0.25 event snapshots: immutable hit Z + current-side-only split rendering",
    "V0.26 frozen hit tails: X/Z remain immutable until opacity reaches zero"
)

out.write_text(text, encoding="utf-8")
print(out)
