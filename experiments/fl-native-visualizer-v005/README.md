# Field V0.05 Stable Visualizer

This test build addresses two readability problems observed in V0.04:

1. The active-track list no longer reorders by momentary peak. It stays in FL mixer-index order.
2. Visual geometry is deliberately persistent rather than block-reactive:
   - spectrum analysis runs at a reduced visual telemetry rate,
   - spectral bands use moderate attack and slow release,
   - stereo balance and width are smoothed,
   - track activity decays gradually so objects do not blink between notes.

Audio reconstruction remains unchanged from the validated V0.03/V0.04 path; only visual telemetry behaviour is changed.
