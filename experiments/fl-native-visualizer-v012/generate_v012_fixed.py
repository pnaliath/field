from pathlib import Path

here = Path(__file__).resolve().parent
original = here / "generate_v012.py"
source = original.read_text(encoding="utf-8")

strict = '''replace_once(
    "        std::vector<DrawTrack> stableList = active;",
    "        std::vector<DrawTrack> stableList = allLearned;",
    "sidebar shows all learned routes",
)'''
flexible = '''import re
sidebar_patterns = [
    r"std::vector<DrawTrack>\\s+(stableList|loudest)\\s*=\\s*active\\s*;",
    r"std::vector<DrawTrack>\\s+(stableList|loudest)\\s*=\\s*renderOrder\\s*;",
]
_sidebar_done = False
for sidebar_pattern in sidebar_patterns:
    m = re.search(sidebar_pattern, text)
    if m:
        var = m.group(1)
        text = text[:m.start()] + "std::vector<DrawTrack> " + var + " = allLearned;" + text[m.end():]
        _sidebar_done = True
        break
if not _sidebar_done:
    for needle in ["maxRows", "[FX RETURN]", "stableList", "loudest", "sidebarLeft"]:
        p = text.find(needle)
        if p >= 0:
            print("\\n--- V0.12 SIDEBAR DEBUG", needle, "---\\n")
            print(text[max(0, p-1000):p+1800])
    raise RuntimeError("V0.12 sidebar structure debug dump above")'''

if strict not in source:
    raise RuntimeError("V0.12 fixed wrapper could not find sidebar strict patch block")
source = source.replace(strict, flexible, 1)

ns = {"__file__": str(original), "__name__": "__main__"}
exec(compile(source, str(original), "exec"), ns, ns)
