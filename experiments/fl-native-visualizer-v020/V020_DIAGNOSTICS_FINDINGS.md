# Field V0.20 diagnostics findings

Source: user reproduction CSV `FieldV020_diagnostics.csv`.

Capture: 4101 rows, 13 routed tracks, ~157.6 s.

## What passed

- Presence decay remains fixed. Median presence while routes were at <= -110 dB is effectively 0 (about 0.0000; p95 about 0.0001).
- Median onset -> actual body draw is ~15 ms.
- Most instrument onsets draw within one paint interval (~15-16 ms).
- The V0.19 multi-second response failure is largely gone.
- The long FFT window improves several sensible source ranges: BASE1 ~30.5-405 Hz, PADS ~171-2273 Hz, 3xOsc ~313-808 Hz, guitar commonly ~72-3814 Hz.

## Remaining response bug

One GUITAR CHORDS onset recorded ~547 ms onset -> draw even though the profile was already ready and onset -> presence was 0 ms. This points to the primary-body/FX-return suppression path still occasionally hiding a normal source. A crash source's first draw was ~110 ms, consistent with initial spectrum-window/profile readiness rather than UI latency.

## New real-time problem introduced by V0.20

The 4096-point FFT currently executes inside the audio render callback.

Unique callback snapshots in this capture:
- median render cost ~0.009 ms
- p99 render cost ~1.157 ms
- max ~1.308 ms
- UI paint median ~16 ms

The host sometimes supplied very small audio blocks (minimum logged block budget ~0.045 ms). During FFT callbacks the logged render percentage therefore exceeded the available block budget (p99 ~355%, max ~675%). Even if no audible glitch was reported in this capture, this is not a production-safe real-time design.

The FFT/profile analysis must move off the audio thread. The audio callback should only feed a lock-free/preallocated analysis queue or snapshot mechanism.

## Spectral geometry status

V0.20 improved some instruments substantially, but the low-frequency problem is not solved globally.

Representative median learned ranges:
- KICK1: 28-222 Hz, dominant ~66 Hz (plausible)
- BASE1: ~30-405 Hz, dominant ~61 Hz (plausible)
- PADS: ~171-2273 Hz, dominant ~525 Hz (plausible)
- 3xOsc: ~313-808 Hz, dominant ~372 Hz (plausible)
- GUITAR CHORDS: commonly ~72-3814 Hz, dominant ~222 Hz (plausible much of the capture)
- HAT1: often 28-18000 Hz, dominant 28 Hz (wrong)
- FLUTE: often 28-18000 Hz, dominant ~405 Hz (low edge/high edge wrong)
- VOCAL: often 28-9031 Hz, dominant ~121 Hz (low edge still overextended)

About 51% of all logged rows still reported a 28 Hz low edge; this is much better than V0.19 (~99.8%) but still unacceptable.

## Root design mismatch with the web app

`ANALYSIS.md` specifies the web visual grammar as:
- 1024-point Hann FFT
- max magnitude bin per logarithmic band
- 82nd percentile across frames
- 1-2-1 smoothing
- shape mapping against a **session-wide reference**: `REF = loudest band across session + 15 dB`, `DYN = 76 dB`, `GATE = 0.095`
- contiguous lobes only, discard runs shorter than 2 bands, merge gaps <= 2 bands

The plugin currently gates each track primarily relative to its own spectral peak. For sparse/transient or very quiet sources this can promote a noise/leakage floor into a full-range body. V0.21 should port the web shape mapping literally instead of further tuning per-track thresholds.

## V0.21 targets

1. Keep the V0.19 fast presence path on the audio thread.
2. Move FFT/profile learning off the audio callback using preallocated lock-free transport/snapshots.
3. Port the web session-reference shape mapping exactly (`REF`, `DYN=76`, `GATE=0.095`, lobe run rules).
4. Do not let uncertain audio-derived FX classification suppress a normal primary body; retain FX association separately until confidence is unambiguous.
5. Keep diagnostics enabled to verify audio-thread cost, onset -> draw, and learned frequency bounds.
