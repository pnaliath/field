# Field V0.33 diagnostic findings

Source: user reproduction CSV `FieldV033_diagnostics.csv`.

Capture: 11,692 rows across 13 routed tracks.

## Confirmed telemetry failure

The V0.33 GDI+ renderer replaced the inherited `drawSpectralBody()` implementation but did not carry forward the V0.18 `stampDiagnosticDraw()` hook. Consequently `onset_to_draw_ms` remained `-1` for every row even though bodies were visibly eligible/rendering.

The inherited `diagVisualZ` write was attached to an older depth/render path. In the V0.33 capture `z` is exactly `0.5` for all 11,692 rows, while live/depth telemetry varies normally. The logged `z` therefore does not describe the DrawTrack consumed by the final GDI+ renderer.

## Why this matters

V0.33 was a renderer-only experiment from the V0.31 behavior base. Diagnostics that observe stale upstream state can make a renderer regression look like a DSP/state regression. Production work must measure the final render snapshot before changing analysis logic.

## V0.34 target

1. Restore onset -> actual body-draw timing at the final GDI+ eligibility point.
2. Stamp the exact final rendered X, Z, width, presence, voice/event identity, and lobe/frequency bounds.
3. Log `routeDisplayProfileReady`, because that is the actual V0.33 body gate rather than only the older raw profile-ready state.
4. Keep all existing CSV columns for direct comparison with V0.18-V0.33.
5. Do not alter DSP, route classification, source behavior, audio reconstruction, or visual grammar.
