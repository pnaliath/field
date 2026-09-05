from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
runpy.run_path(str(here / "generate_v033.py"), run_name="__main__")
out = here / "generated" / "fieldv033.cpp"
text = out.read_text(encoding="utf-8")
old = "std::array<Gdiplus::PointF, kRingSegments + 1> pts {};"
if old not in text:
    raise RuntimeError("V0.33 GDI+ ring array marker not found")
text = text.replace(old, "std::array<Gdiplus::PointF, 19> pts {};", 1)
out.write_text(text, encoding="utf-8")
print(out)
