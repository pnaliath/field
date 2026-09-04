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

# drawIdentityTrace is between drawSpectralBody and drawTrackNameOnBody in V0.16,
# so the V0.17 body replacement already removes that old full-height function.
# Remove the redundant generator patch that tried to remove it a second time.
identity_start = code.find("# Current V0.12 identity trace closes a full-range polygon.")
identity_end = code.find("# Label the dominant occupied band", identity_start)
if identity_start < 0 or identity_end < 0:
    raise RuntimeError("V0.17 fixed wrapper could not isolate redundant identity patch")
code = code[:identity_start] + code[identity_end:]

# The inherited paint pass still contains an identity-trace call. Since the ring stack
# and per-lobe silhouette replace that overlay, remove the call from final generated C++.
write_marker = 'out.write_text(text, encoding="utf-8")'
if write_marker not in code:
    raise RuntimeError("V0.17 fixed wrapper could not find generator output marker")
cleanup = '''text = text.replace(\n    "        for (const auto& track : renderOrder)\\n            drawIdentityTrace (dc, track, fieldArea);\\n",\n    ""\n)\n\n'''
code = code.replace(write_marker, cleanup + write_marker, 1)

namespace = {"__file__": str(script), "__name__": "__main__"}
exec(compile(code, str(script), "exec"), namespace)
