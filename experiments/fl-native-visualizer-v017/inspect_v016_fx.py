from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v016 = root / "fl-native-visualizer-v016"
runpy.run_path(str(v016 / "generate_v016_fixed.py"), run_name="__main__")
text = (v016 / "generated" / "fieldv016.cpp").read_text(encoding="utf-8")
start = text.find("    void drawFxAura")
end = text.find("    void fxAmountsForSource", start)
print("START", start, "END", end)
print(text[start:end + 300] if start >= 0 and end >= 0 else text[max(0,start):max(0,start)+5000])
