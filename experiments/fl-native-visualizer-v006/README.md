# Field V0.06 FX Aware Visualizer

Builds on validated V0.05 FL-native single-instance reconstruction.

Changes:
- Any route that produces meaningful audio is latched into the sidebar for the rest of the plugin session, in FL mixer order.
- Maintains short envelope history per routed input.
- Classifies temporal FX returns from delayed/diffuse correlation rather than relying on track names.
- Reverb-like returns render as expanded faded halos around likely source objects.
- Delay-like returns render as faded offset echo contours around likely source objects.
- Temporal FX return audio remains in the reconstructed mix exactly once; only the visualization is attached to source objects.
- Track-name hints (reverb/delay/etc.) are weak confidence boosts only, not the primary detector.

This is still a heuristic prototype. Group buses and zero-lag parallel processing should remain ordinary objects rather than being classified as temporal FX returns.
