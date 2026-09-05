from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
source = (here / "generate_v025.py").read_text(encoding="utf-8")

old = '''replace_once(
    "    void drawTrackNameOnBody (HDC dc, const DrawTrack& track, const RECT& area)\\n    {\\n        if (!track.meta)",
    "    void drawTrackNameOnBody (HDC dc, const DrawTrack& track, const RECT& area)\\n"
    "    {\\n"
    "        if (!track.renderLabel)\\n"
    "            return;\\n"
    "        if (!track.meta)",
    "suppress duplicate snapshot labels",
)'''
new = '''replace_once(
    "    void drawTrackNameOnBody (HDC dc, const DrawTrack& track, const RECT& area)\\n    {",
    "    void drawTrackNameOnBody (HDC dc, const DrawTrack& track, const RECT& area)\\n"
    "    {\\n"
    "        if (!track.renderLabel)\\n"
    "            return;",
    "suppress duplicate snapshot labels",
)'''
if old not in source:
    raise RuntimeError("V0.25 fixed wrapper could not find label patch source block")
source = source.replace(old, new, 1)

temp = here / "_generate_v025_stable.py"
temp.write_text(source, encoding="utf-8")
runpy.run_path(str(temp), run_name="__main__")
print(here / "generated" / "fieldv025.cpp")
