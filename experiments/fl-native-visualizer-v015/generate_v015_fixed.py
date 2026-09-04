from pathlib import Path

script = Path(__file__).resolve().parent / "generate_v015.py"
code = script.read_text(encoding="utf-8")

old = '''# Do not draw an unlearned half-random body while the histogram has only a few frames.
replace_once(
    "        const size_t routeIndex = static_cast<size_t> (route - 1);\\n\\n        const float halfDepth",
    "        const size_t routeIndex = static_cast<size_t> (route - 1);\\n"
    "        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))\\n"
    "            return;\\n\\n"
    "        const float halfDepth",
    "body waits for learned profile",
)
'''

new = '''# Do not draw an unlearned half-random body while the histogram has only a few frames.
replace_once(
    "        if (route < 1 || route > kMaxRoutes)\\n            return;\\n\\n        const float halfDepth",
    "        if (route < 1 || route > kMaxRoutes)\\n"
    "            return;\\n"
    "        const size_t routeIndex = static_cast<size_t> (route - 1);\\n"
    "        if (!routeProfileReady[routeIndex].load (std::memory_order_relaxed))\\n"
    "            return;\\n\\n"
    "        const float halfDepth",
    "body waits for learned profile",
)
'''

if old not in code:
    raise RuntimeError("V0.15 fixed wrapper could not find body readiness patch")
code = code.replace(old, new, 1)

namespace = {"__file__": str(script), "__name__": "__main__"}
exec(compile(code, str(script), "exec"), namespace)
