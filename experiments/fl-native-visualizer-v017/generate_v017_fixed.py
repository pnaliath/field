from pathlib import Path

script = Path(__file__).resolve().parent / "generate_v017.py"
code = script.read_text(encoding="utf-8")
old = 'runpy.run_path(str(v016 / "generate_v016.py"), run_name="__main__")'
new = 'runpy.run_path(str(v016 / "generate_v016_fixed.py"), run_name="__main__")'
if old not in code:
    raise RuntimeError("V0.17 fixed wrapper could not find V0.16 generator call")
code = code.replace(old, new, 1)
namespace = {"__file__": str(script), "__name__": "__main__"}
exec(compile(code, str(script), "exec"), namespace)
