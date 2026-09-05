from pathlib import Path

here = Path(__file__).resolve().parent
original = here / "generate_v011.py"
source = original.read_text(encoding="utf-8")
source = source.replace(
    '    "    void fxAmountsForSource",\n    room_fx,\n    "3D room FX aura",',
    '    "    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)",\n    room_fx,\n    "3D room FX aura",',
    1,
)
ns = {"__file__": str(original), "__name__": "__main__"}
exec(compile(source, str(original), "exec"), ns, ns)
