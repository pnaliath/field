# Field V0.32 — Instant Stable Shape

Scope:
- first valid full FFT frame publishes a sanitized provisional body
- frames 2-4 refine quickly, then display geometry adapts extremely slowly
- per-source Z is captured once per sounding segment and held until silence
- lower-chatter presence smoothing
- preserves V0.31 stable dual-voice topology
- X 0.95x, Z 1.20x, disappear 500 ms inherited

Known technical debt: the inherited 4096-point FFT still runs on the audio thread. This build fixes the visible geometry/presence/depth regressions first; FFT worker migration remains required for final performance hardening.
