from pathlib import Path

here = Path(__file__).resolve().parent
source_path = here / "generate_v006.py"
code = source_path.read_text(encoding="utf-8")

fixes = [
    (
        '''    "                band.store (0.0f, std::memory_order_relaxed);\\n\\n"\n    "        updateBandCoefficients (44100.0f);",''',
        '''    "                band.store (0.0f, std::memory_order_relaxed);\\n"\n    "        updateBandCoefficients (44100.0f);",''',
    ),
    (
        '''    "            refreshMetadata ();\\n"\n    "        }\\n\\n"\n    "        if (editorWindow)",''',
        '''    "            refreshMetadata ();\\n"\n    "        }\\n"\n    "        if (editorWindow)",''',
    ),
    (
        '''    "            reportedRouteCount.load (std::memory_order_relaxed), 0, kMaxRoutes);\\n\\n"\n    "        for (int route = 0; route < count; ++route)",''',
        '''    "            reportedRouteCount.load (std::memory_order_relaxed), 0, kMaxRoutes);\\n"\n    "        for (int route = 0; route < count; ++route)",''',
    ),
]

for old, new in fixes:
    if old not in code:
        raise RuntimeError(f"Could not find V0.06 generator patch literal: {old[:70]}")
    code = code.replace(old, new, 1)

globals_dict = {"__file__": str(source_path), "__name__": "__main__"}
exec(compile(code, str(source_path), "exec"), globals_dict, globals_dict)
