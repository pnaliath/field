# V0.16 visual feedback checkpoint — 2026-09-04

User-confirmed issues before the next visual reset:

1. Z is incorrectly relative across tracks. Lowering one instrument's volume moves other instruments in Z. Existing objects must not move because another track changes level.
2. Spectral bodies incorrectly extend down to the floor / lowest frequency even when the source has no low-frequency energy (e.g. hats). Body vertical extent must follow the actually occupied spectral range.
3. Presence is inconsistent across repeated hits/notes: an instrument may appear on some hits and not others. Geometry identity must remain stable; activity/presence requires reliable attack/hold/release behavior.
4. The next renderer should explicitly match the browser/web prototype references: translucent layered 3D spectral bodies, frequency-cropped extents, stable room placement, shadows, and track labels attached to bodies.

Reference implementation rule for the next build: do not normalize Z using the set of currently learned tracks. Use each track's own absolute long-term loudness mapping, with fixed calibration and clamping.
