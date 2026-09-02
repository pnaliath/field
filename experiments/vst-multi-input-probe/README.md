# Field Multi-Input Probe

Diagnostic VST3 for testing a **single Field instance with multiple independent DAW tracks**.

## What it exposes

- 8 stereo input buses
  - Input 1 = main input
  - Inputs 2..8 = auxiliary/sidechain inputs
- 1 stereo `Field Mix` output = unattenuated sum of all active inputs
- 8 stereo `Stem Out` auxiliary outputs = one mirror per input
- Windows diagnostic editor with live RMS/peak meters for each input

The plugin does not perform Field DSP yet. Its purpose is to prove or disprove the routing topology before building the real plugin.

## FL Studio test

1. Load **one** `Field Multi-Input Probe` instance on a dedicated mixer insert, e.g. `FIELD HUB`.
2. Open the plugin Wrapper processing/input routing controls.
3. Route different FL mixer tracks into different plugin input/sidechain buses.
4. Play audio.
5. Open the plugin editor.
6. Verify that Input 1..8 rows light independently according to the tracks you routed.

Success criterion: two or more different source mixer tracks can drive different Field input rows independently while only one Field VST3 instance exists.

## Important

`Field Mix` simply sums the active inputs without attenuation and can clip. This is a diagnostic build, not a mixing plugin.
