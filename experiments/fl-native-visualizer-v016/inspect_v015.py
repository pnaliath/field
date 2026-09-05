from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v015 = root / "fl-native-visualizer-v015"
runpy.run_path(str(v015 / "generate_v015_fixed.py"), run_name="__main__")
src = v015 / "generated" / "fieldv015.cpp"
text = src.read_text(encoding="utf-8")
lines = text.splitlines()

needles = [
    "LEARNED TRACKS",
    "active.push_back",
    "everActive",
    "drawSpectralBody",
    "drawIdentityTrace",
    "frontFill",
    "presence =",
    "peakDb",
    "renderOrder",
    "shouldHideAsFxVisualReturn",
]

seen = set()
for needle in needles:
    print(f"\n===== {needle} =====")
    for i, line in enumerate(lines):
        if needle in line:
            a = max(0, i - 18)
            b = min(len(lines), i + 30)
            key = (a,b)
            if key in seen:
                continue
            seen.add(key)
            for j in range(a,b):
                print(f"{j+1:04d}: {lines[j]}")
            print("---")
