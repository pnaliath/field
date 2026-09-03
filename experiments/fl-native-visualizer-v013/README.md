# Field V0.13 — Stable Depth + Axis Controls

Built on V0.12 after in-DAW feedback.

Changes in this test build:
- `Invert X` and `Invert Y` checkboxes in the top bar. Defaults remove V0.12's hard-coded inversions.
- Z depth is no longer driven by peak level/gain or momentary stereo width. It uses a latched dry/delay/reverb/both topology class with hysteresis, so ordinary playing dynamics should not move objects front/back.
- `AUX` is recognized as an FX-return naming hint, but source-associated temporal evidence is still required before suppression.
- High-confidence FX returns remain learned internally but are removed from the `PRIMARY TRACKS` list and standalone spectral bodies; their effect is shown on the associated source instead.
- Audio reconstruction path is unchanged from V0.12.

Validation targets:
1. Reverb AUX should not read as a separate primary instrument once learned.
2. No visible Z pumping from ordinary gain/dynamics when routing is unchanged.
3. X/Y orientation can be corrected independently from the UI without a rebuild.
