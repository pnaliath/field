# Field V0.20 plan

Measured target: fix universal 28 Hz occupancy without reintroducing visual-response latency.

- Keep V0.19 block-safe fast presence path unchanged.
- Accumulate every routed source into a 4096-sample mono analysis ring buffer.
- Remove DC and apply Hann window before spectral analysis.
- Use a radix-2 4096-point FFT, then map the 76 log bands from the FFT bins.
- Geometry/profile updates remain slower than presence; presence stays block-fast.
- Preserve V0.19 diagnostics in `%TEMP%\FieldV020_diagnostics.csv`.
