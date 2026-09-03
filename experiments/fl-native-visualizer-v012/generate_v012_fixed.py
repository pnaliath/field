from pathlib import Path

here = Path(__file__).resolve().parent
original = here / "generate_v012.py"
source = original.read_text(encoding="utf-8")

# The inherited V0.11 sidebar already rebuilds its own stable list directly from
# inputs + everActive, independent of the primary-body `active` vector. Keep it
# that way: this is exactly what V0.12 needs for an all-learned route list.
strict = '''replace_once(
    "        std::vector<DrawTrack> stableList = active;",
    "        std::vector<DrawTrack> stableList = allLearned;",
    "sidebar shows all learned routes",
)'''
replacement = '''# Sidebar intentionally remains independent: inherited V0.11 already builds
# stableList from every input whose everActive latch is true.'''

if strict not in source:
    raise RuntimeError("V0.12 fixed wrapper could not find obsolete sidebar patch block")
source = source.replace(strict, replacement, 1)

ns = {"__file__": str(original), "__name__": "__main__"}
exec(compile(source, str(original), "exec"), ns, ns)
