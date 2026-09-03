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
sidebar_pattern = r"std::vector<DrawTrack>\\s+(stableList|loudest)\\s*=\\s*active\\s*;"
_sidebar_hits = re.findall(sidebar_pattern, text)
if not _sidebar_hits:
    raise RuntimeError("V0.12 could not find inherited sidebar list assignment")
text = re.sub(sidebar_pattern, lambda m: "std::vector<DrawTrack> " + m.group(1) + " = allLearned;", text, count=1)'''

if strict not in source:
    raise RuntimeError("V0.12 fixed wrapper could not find sidebar strict patch block")
source = source.replace(strict, flexible, 1)

ns = {"__file__": str(original), "__name__": "__main__"}
exec(compile(source, str(original), "exec"), ns, ns)
