from pathlib import Path

script = Path(__file__).resolve().parent / "generate_v017.py"
code = script.read_text(encoding="utf-8")

old = 'runpy.run_path(str(v016 / "generate_v016.py"), run_name="__main__")'
new = 'runpy.run_path(str(v016 / "generate_v016_fixed.py"), run_name="__main__")'
if old not in code:
    raise RuntimeError("V0.17 fixed wrapper could not find V0.16 generator call")
code = code.replace(old, new, 1)

# In stabilized V0.16, drawFxAura is immediately followed by drawSpectralBody.
old_fx_end = '    "    bool shouldHideAsFxVisualReturn",\n    fx_body,'
new_fx_end = '    "    void drawSpectralBody",\n    fx_body,'
if old_fx_end not in code:
    raise RuntimeError("V0.17 fixed wrapper could not find FX replacement boundary")
code = code.replace(old_fx_end, new_fx_end, 1)

# drawIdentityTrace lives between drawSpectralBody and drawTrackNameOnBody in V0.16.
# The V0.17 spectral-body replacement therefore consumes the old identity function.
# Keep the existing paint call valid with a no-op stub inside the replacement itself,
# and remove the redundant second attempt to patch the already-consumed function.
ring_tail = '''        SelectObject (dc, oldBrush); SelectObject (dc, oldPen); DeleteObject (silhouettePen);\n    }\n\n'''\nreplace_between(\n    "    void drawSpectralBody'''
ring_tail_with_stub = '''        SelectObject (dc, oldBrush); SelectObject (dc, oldPen); DeleteObject (silhouettePen);\n    }\n\n    void drawIdentityTrace (HDC, const DrawTrack&, const RECT&)\n    {\n        // Ring stack and independent lobe silhouettes already provide identity/readability.\n    }\n\n'''\nreplace_between(\n    "    void drawSpectralBody'''
if ring_tail not in code:
    raise RuntimeError("V0.17 fixed wrapper could not find ring renderer tail")
code = code.replace(ring_tail, ring_tail_with_stub, 1)

identity_start = code.find("# Current V0.12 identity trace closes a full-range polygon.")
identity_end = code.find("# Label the dominant occupied band", identity_start)
if identity_start < 0 or identity_end < 0:
    raise RuntimeError("V0.17 fixed wrapper could not isolate redundant identity patch")
code = code[:identity_start] + code[identity_end:]

namespace = {"__file__": str(script), "__name__": "__main__"}
exec(compile(code, str(script), "exec"), namespace)
