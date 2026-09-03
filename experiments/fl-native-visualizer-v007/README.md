# Field V0.07 FX Aware Visualizer

Builds on V0.06 after in-DAW feedback showed a reverb return still rendering as a standalone object.

Changes:
- keeps the persistent mixer-order track list
- expands temporal observation history
- adds level-independent 24-band spectral similarity to source/return matching
- combines delayed envelope correlation, tail persistence, spectral identity and stereo diffusion
- keeps name hints as weak evidence only; adds common short aliases such as REV/RVB/DEL/DLY
- classified reverb returns render as faded halos around likely source objects
- classified delay returns render as faded echo contours
- zero-lag buses should remain standalone primary objects
- audio reconstruction path remains unchanged

Validation goal: an FX return should stop occupying a standalone spectral body after enough audio history is collected, while the wet layer appears around its likely source object(s).