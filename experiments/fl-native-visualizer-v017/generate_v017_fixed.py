from pathlib import Path

script = Path(__file__).resolve().parent / "generate_v017.py"
code = script.read_text(encoding="utf-8")

old = 'runpy.run_path(str(v016 / "generate_v016.py"), run_name="__main__")'
new = 'runpy.run_path(str(v016 / "generate_v016_fixed.py"), run_name="__main__")'
if old not in code:
    raise RuntimeError("V0.17 fixed wrapper could not find V0.16 generator call")
code = code.replace(old, new, 1)

# In the stabilized V0.16 generated source drawFxAura is immediately followed by
# drawSpectralBody. The first V0.17 generator used an older classifier marker as
# the replacement boundary, so configuration stopped before C++ compilation.
old_fx_end = '    "    bool shouldHideAsFxVisualReturn",\n    fx_body,'
new_fx_end = '    "    void drawSpectralBody",\n    fx_body,'
if old_fx_end not in code:
    raise RuntimeError("V0.17 fixed wrapper could not find FX replacement boundary")
code = code.replace(old_fx_end, new_fx_end, 1)

namespace = {"__file__": str(script), "__name__": "__main__"}
exec(compile(code, str(script), "exec"), namespace)
