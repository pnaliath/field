# Field V0.19 validation against V0.18 diagnostics

Source: user reproduction CSVs `FieldV018_diagnostics.csv` and `FieldV019_diagnostics.csv`.

## Fixes that passed

- Silent visual presence no longer freezes. V0.18 silent median presence was ~0.938; V0.19 silent median is ~0.0001.
- End-to-end onset -> body draw latency collapsed from a 5.375 s worst case to 110 ms worst case in this capture.
- Median onset -> draw remains ~15-16 ms.
- Onset -> presence remains effectively immediate in the diagnostic clock.
- Native render cost remains negligible (V0.19 median ~0.001 ms; p99 ~0.091 ms).
- Paint cadence remains roughly one frame / 16 ms, with occasional 31-46 ms UI frames.

## Remaining measured problem

The tightened occupancy gate improved the high-frequency edge, but the low edge is still wrong:

- every learned V0.19 sample still reports `low_hz = 28`.
- high edge is no longer universally 18 kHz; many samples now stop around 16.5 kHz, 2.48 kHz, 2.70 kHz, etc.

This indicates the remaining low-frequency problem is not primarily a display threshold problem. The current analyzer runs Goertzel independently on short DAW audio blocks. At 44.1/48 kHz, a 28 Hz cycle is ~1575/1714 samples, so short host buffers do not contain enough cycles to estimate the low bands reliably. Leakage/DC therefore makes the 28 Hz band look occupied.

## V0.20 target

Replace short-block spectral estimation with a long analysis window (4096 samples), windowing + DC removal, and a proper frequency-domain readout for the 76 log bands. Keep the fast presence path independent so visual onset response does not inherit the longer geometry-analysis window.
