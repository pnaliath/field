# Field V0.14 visual behavior fixes

Test scope:
- Invert X/Y controls change mouse orbit drag direction only; room axis semantics and labels stay fixed.
- Assign Field's own high-separation stable palette per mixer route instead of relying on similar FL mixer colours.
- Hold each learned source's last valid spatial pose when its audio stops; silence must not snap the object to the front of the room.
- Detect and visualize genuinely quiet routed audio below the previous learned-route floor using separate existence and display normalization thresholds.
- Preserve validated one-instance FL-native reconstruction and FX-return attachment behavior.
