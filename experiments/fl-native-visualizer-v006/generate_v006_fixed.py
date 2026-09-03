from pathlib import Path

here = Path(__file__).resolve().parent
source_path = here / "generate_v006.py"
code = source_path.read_text(encoding="utf-8")

old = '''    "                band.store (0.0f, std::memory_order_relaxed);\\n\\n"\n    "        updateBandCoefficients (44100.0f);",'''
new = '''    "                band.store (0.0f, std::memory_order_relaxed);\\n"\n    "        updateBandCoefficients (44100.0f);",'''

if old not in code:
    raise RuntimeError("Could not find V0.06 history-initialization patch literal")
code = code.replace(old, new, 1)

globals_dict = {"__file__": str(source_path), "__name__": "__main__"}
exec(compile(code, str(source_path), "exec"), globals_dict, globals_dict)
