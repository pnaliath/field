from pathlib import Path

script = Path(__file__).resolve().parent / "generate_v016.py"
code = script.read_text(encoding="utf-8")

old = '''# FX haze/echo must follow the source activity too; otherwise a paused session can
# still display floating return auras after the body disappears.
replace_once(
    "        if (!track.meta || (reverbAmount <= 0.01f && delayAmount <= 0.01f))\\n            return;",
    "        if (!track.meta || (reverbAmount <= 0.01f && delayAmount <= 0.01f))\\n"
    "            return;\\n"
    "        const float sourcePresence = visualPresenceForTrack (track);\\n"
    "        if (sourcePresence <= 0.012f)\\n"
    "            return;\\n"
    "        reverbAmount *= sourcePresence;\\n"
    "        delayAmount *= sourcePresence;",
    "FX aura follows source presence",
)
'''

new = '''# FX haze/echo must follow the source activity too; otherwise a paused session can
# still display floating return auras after the body disappears. Inject immediately
# after the stable function header instead of relying on inherited early-return text.
replace_once(
    "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)\\n    {",
    "    void drawFxAura (HDC dc, const DrawTrack& track, const RECT& area, float reverbAmount, float delayAmount)\\n"
    "    {\\n"
    "        const float sourcePresence = visualPresenceForTrack (track);\\n"
    "        if (sourcePresence <= 0.012f)\\n"
    "            return;\\n"
    "        reverbAmount *= sourcePresence;\\n"
    "        delayAmount *= sourcePresence;",
    "FX aura follows source presence",
)
'''

if old not in code:
    raise RuntimeError("V0.16 fixed wrapper could not find FX aura patch block")
code = code.replace(old, new, 1)

namespace = {"__file__": str(script), "__name__": "__main__"}
exec(compile(code, str(script), "exec"), namespace)
