# Field V0.09 Recovering FX Visualizer

Supersedes V0.08 after in-DAW validation showed that indefinite sticky FX links could eventually hide normal instruments and leave the primary visual field empty.

Changes:
- FX-return identity now uses confidence + hysteresis rather than permanent retention.
- A return must be repeatedly supported before it is hidden as an FX return.
- Silent periods do not erase a learned return.
- Active contradictory evidence gradually removes a false-positive FX classification.
- Previous source links are retained only while confidence remains latched.
- Primary audio-bearing objects remain session-persistent once learned.
- Safety fallback prevents the entire visual field from becoming empty because of classifier mistakes.
- Unity reconstruction path remains unchanged.
