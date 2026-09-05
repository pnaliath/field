# Field V0.18 response diagnostics findings

Source: user reproduction CSV (`FieldV018_diagnostics.csv`), 539 samples over ~97.5 seconds, 3 routed tracks.

## What is NOT causing the perceived lag

- Native render cost is tiny: median ~0.001 ms, p99 ~0.059 ms, max ~0.067 ms.
- Paint cadence is ~15-16 ms (~60 Hz).
- Onset -> presence telemetry is 0 ms in this capture.

This is not a CPU/block-overrun problem and not a slow paint-loop problem.

## Confirmed state bugs

### 1. Presence freezes when FL stops marking a route buffer `IO_Filled`

Silent rows (`peak <= -110 dB`) still retain very high presence:

- Route 1: median presence ~0.954 while silent
- Route 2: median presence ~0.763 while silent
- Route 3: median presence ~0.938 while silent

The current per-route presence update lives after `GetInBuffer`/`IO_Filled` gating. If a route is not filled for a block, the loop `continue`s before presence can decay. Therefore the last visual state can remain frozen for seconds.

### 2. Primary-body visibility can be delayed by FX-return suppression

Route 2 recorded onset -> draw delays up to ~5375 ms even though onset -> presence was 0 ms and its learned profile was already ready. This means audio/presence responded, but the object was not actually painted for several seconds. The likely gating stage is primary-body suppression from the temporal FX-return classifier/hysteresis.

This matches the reported behaviour where some instruments appear on some hits and disappear on others.

### 3. First profile learning is measurable but not the main multi-second lag

Initial onset -> profile-ready latency:

- Route 1: ~157 ms
- Route 2: ~172 ms
- Route 3: already learned in the sampled window

That startup learning delay is real, but it does not explain the ~5.4 s body-draw stalls.

### 4. Frequency occupancy gate is too permissive

For 537/539 samples, diagnostics reported `low_hz=28` and `high_hz=18000`.

So despite the lobe renderer, the current learned-shape gate still considers essentially the full band range occupied. The renderer is cropping geometrically, but the spectral occupancy model is not yet discriminating enough.

## V0.19 fix targets

1. Decay visual presence every audio block, including routes with no `IO_Filled` buffer.
2. Do not allow uncertain FX classification to suppress a primary body for seconds; require stronger/longer confirmation before hiding.
3. Preserve fast onset response independent of the long-term shape learner.
4. Tighten spectral occupancy using an absolute + relative threshold so hats/high-frequency sources do not acquire 28 Hz floor content from leakage/noise.
5. Keep V0.18 diagnostics available in the next test build so each fix can be verified quantitatively.
