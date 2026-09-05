# Field V0.11 — Room Space Visualizer

FL Studio native experiment that keeps the validated single-instance routed-audio reconstruction and V0.09 FX-return classifier, while replacing arbitrary view-only Z stacking with the browser prototype's room model.

## Visual mapping

- X: measured stereo balance / pan
- Y: log-frequency height, 70 Hz to 16 kHz
- Z: inferred apparent acoustic depth from attached temporal wetness, level, and stereo diffuseness
- Spectral bodies are extruded along Z so they read as 3D volumes rather than flat polygons
- Reverb/delay layers occupy nearby room depth instead of becoming standalone primary bodies

The Z estimate is perceptual/inferred from the audio reaching Field; it is not a DAW routing index and V0.11 does not change audio based on Z.

## Controls

- Drag inside room: orbit
- Mouse wheel: zoom
- Double click: reset to the browser-style three-quarter view
