# V0.19 measured fix plan

1. Presence decay runs every audio block, even if a route is not `IO_Filled`.
2. Uncertain FX-return classification cannot hide primary bodies; thresholds become substantially more conservative.
3. Spectral occupancy dynamic range is tightened so learned lobes do not default to 28 Hz-18 kHz.
4. V0.18 response diagnostics remain enabled and write a V0.19 CSV for verification.
5. Audio reconstruction path remains unchanged.
