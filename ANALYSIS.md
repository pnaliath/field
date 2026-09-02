# Field — analysis specification

This is the part of Field that has to survive the move to C++. The renderer can
be rebuilt; these algorithms and constants are the product.

Every value here is taken from the working prototype in `index.html`. Where a
number looks arbitrary it usually is not — most were tuned against measurements,
and the reasoning is recorded alongside.

The right-hand column of each section describes what changes inside a plugin,
where you never receive the whole file. See **Streaming** at the end.

---

## 0. Band grid

Everything is expressed on a fixed logarithmic band grid.

```
FMIN   = 28 Hz
FMAX   = 18000 Hz
NBANDS = 76
bandF[i] = FMIN * (FMAX/FMIN)^(i / (NBANDS-1))
```

Band edges for FFT folding are the geometric means of adjacent centres. Within a
band, take the **maximum** magnitude bin, not the mean — the mean smears narrow
resonances that matter.

---

## 1. Long-term spectrum (the shape)

The static outline of a sound. Measured once, never animated.

```
FFT size   1024, Hann window
hop        max(192, floor((len - 1024) / 340))    ~340 frames per file
input      mono sum, (L + R) * 0.5
magnitude  sqrt(re² + im²) / (N * 0.25)
```

For each band, collect its value across all frames, sort, and take the
**82nd percentile**, then convert to dB.

> Percentile rather than mean is the single most important choice here. A hi-hat
> that sounds on eighths is silent most of the time; averaging buries it and the
> shape comes out wrong. The 82nd percentile asks "how loud is this band when
> this sound is actually happening".

Then smooth across bands with a 1-2-1 kernel so the outline reads as a body
rather than a comb.

---

## 2. Amplitude envelope

```
rate  100 Hz (hop = sampleRate / 100)
value RMS of the hop window, mono sum
      normalised so the loop peak is 1.0
```

Used for three things: deciding when a shape is lit, deciding whether two sounds
ever coincide, and detecting onsets.

---

## 3. Onsets

```
for i in 2 .. n-1:
    e[i] > 0.15                      absolute floor
and e[i] > e[i-1] * 1.25             a real rise
and e[i-1] >= e[i-2] * 0.9           not already falling
and i - last > 0.06 * rate           60 ms minimum gap
```

Each onset's **end** is where its own sound decays, not where the next onset
begins:

```
peak = max(e) over the first 50 ms after the onset
end  = first frame where e < max(0.05, peak * 0.22), capped at the next onset
```

> Getting this wrong was a real bug. Ending each event at the next onset made
> alternating hi-hats appear lit 86% of the time simultaneously. With decay-based
> ends they alternate correctly, at 0%.

---

## 4. Voices — splitting a track by position

A track is not necessarily one object. Hits that land in different places in the
stereo field become separate shapes with separate envelopes.

For each onset, over its event window:

```
pan = (rmsR - rmsL) / (rmsR + rmsL),  clamped to [-1, 1]
weight = (rmsL + rmsR) / 2
```

Bail out to a single voice if there are fewer than 4 events, or if the
weighted standard deviation of pan is below **0.07**.

Otherwise try 1-D k-means with k = 3, then k = 2. A clustering is accepted only
if **both** hold:

```
adjacent centres differ by >= 0.16
every cluster holds >= 12% of the total weight
```

Each accepted cluster becomes a voice with:

- its own spectrum, measured from **only that cluster's sample ranges** (§1)
- its own envelope: the track envelope gated to its own events, with a
  **100 ms** release ramp
- a pan offset equal to the cluster centre

> This tested well: users understood the split immediately, with no explanation.
> It is also the feature most dependent on having the whole file, which makes it
> the main constraint on the plugin architecture.

---

## 5. Loudness (the depth axis)

Not peak level. Peak comes out nearly identical for every track, because every
track has some band near its own maximum — measured spread was 0.43 on a
six-track session, versus 0.81 for the metric below.

K-weighting, at **half strength**:

```
shelf(f) = 4.0 / (1 + (1681/f)²)
hp(f)    = 40 * log10( f / sqrt(f² + 38²) )
K(f)     = (shelf + hp) * 0.55
```

> Full K-weighting is calibrated for programme loudness and buries a kick, which
> is not how a kick sits in a mix. Half strength keeps low end legible.

Per voice:

```
duty   = fraction of frames where env > 0.09, clamped to [0.02, 1]
loudDb = 10*log10( Σ 10^((spectrum[i] + K[i]) / 10) ) + 4*log10(duty)
```

> The duty term is `4*log10`, not `10*log10`. The stronger version crushed
> percussion — a snare that plays 13% of the time is not 9 dB quieter to the ear.

Normalise across the session's own range, padded so nothing pins flat against
either end:

```
span     = clamp(max - min, 14, 42)
LOUD_LO  = min - span * 0.12
LOUD_SPAN= (max - min) + span * 0.24
levelNorm = (loudDb + trimDb - LOUD_LO) / LOUD_SPAN
```

---

## 6. Shape mapping

```
DYN   = 76 dB       visual dynamic range
REF   = (loudest band across the session) + 15 dB headroom
GATE  = 0.095
shape[i] = clamp((spectrumDb[i] + eqDb[i] - (REF - DYN)) / DYN, 0, 1)
```

> The 15 dB headroom matters. Without it the loudest bands sit at exactly 1.0,
> and boosting or sculpting outward does visibly nothing.

**Lobes.** Contiguous runs where `shape > GATE`, discarding runs shorter than 2
bands, merging runs separated by 2 bands or fewer. A track occupies only the
frequencies it really contains — a snare correctly reads as a body around
86–313 Hz plus a separate crack above 1.5 kHz.

**Body radius**, in pan units, with a semicircular taper across each lobe so it
reads as a solid rather than a ribbon:

```
u      = position across the lobe, -1 .. 1
round  = sqrt(1 - u² * 0.94)
halfPan = baseHalf * shape[i]^0.55 * round
zRadius = halfPan / zSpan * (0.5 + 0.85 * levelNorm)
```

Dividing by `zSpan` is what makes a body with equal pan and gain come out
actually round rather than an egg.

---

## 7. Masking

Deliberately much stricter than the drawing threshold. `MASK_GATE = 0.42`
against `GATE = 0.095` — a faint tail is not a collision.

Per pair of voices, per band:

```
skip unless shape_a >= MASK_GATE and shape_b >= MASK_GATE
skip unless the pan intervals overlap

bandLevel = loudLU + (shape - 1) * DYN
rivalry   = exp( -((bandLevel_a - bandLevel_b) / 11)² )
skip if rivalry < 0.12

severity += min(1, overlap / (2 * min(halfA, halfB)))
          * min(shape_a, shape_b)
          * rivalry
```

Then scaled by two whole-signal factors:

```
co-occurrence  fraction of time both voices are above 0.09, sampled 600 times
depth          1 - min(1, |depthA - depthB| * 1.15),  applied as (0.35 + 0.65 * dz)
```

Report if `severity * sensitivity > 1.6`.

> Masking is **not symmetric**, and treating it as such was the reason the
> display over-reported. Two sounds 25 dB apart are not fighting — one has
> already won, which is a different problem and should not be flagged as this one.

**This is a UX heuristic, not an acoustic measurement.** Pan is inferred from L/R
energy, which ignores phase, correlation and precedence. Do not market it as a
masking detector.

---

## 8. Depth macro

Travel is normalised on each side of a track's natural position, so every track
has the full move available in both directions regardless of where it starts.

```
offset = (depth - depth0) / (depth > depth0 ? 1 - depth0 : depth0)
trim   = offset >= 0 ? offset * 10 dB : offset * 22 dB
air    = offset >= 0 ? offset * 4 dB  : offset * 13 dB   (high shelf, 4.5 kHz)
```

`depth0` is clamped to [0.2, 0.78] so neither end is ever unreachable.

Reverb is **not** part of this. It is an independent control.

---

## 9. Curve fitting

The drawn EQ curve is realised as real filters by greedy peak-picking on the
residual:

```
repeat up to MAX_EQ (14):
    find the band with the largest |residual|
    stop if below 1.1 dB
    walk outward while the residual stays above half the peak
    octaves = log2(f_hi / f_lo)
    Q  = clamp(1.4 / octaves, 0.3, 9)
    dB = clamp(peak, -30, 24)
    subtract that filter's response from the residual
```

A single stroke may move a band at most **15 dB** from where it started, and the
refit is throttled to every 110 ms during a stroke. Both exist so cause and
effect stay legible; without them a small stroke rearranged filters the user had
never touched.

Carves are separate from drawn EQ — up to 4 independent notches, so resolving a
collision at 300 Hz does not move the notch at 3 kHz.

---

## Streaming — what changes inside a plugin

A plugin never receives the file. It receives blocks in real time. The host does
provide the transport position, which is what makes this tractable: a profile can
be built against project time over a single playthrough.

| Stage | Offline (today) | Learn pass (plugin) |
|---|---|---|
| Spectrum | sort all frames, take 82nd percentile | per-band running histogram, ~64 log-spaced bins; read the percentile off the histogram. Constant memory, no sort. |
| Envelope | array over the file | array indexed by project time at 100 Hz. ~60 KB per track for 5 minutes. |
| Onsets | one pass over the envelope | same test, applied incrementally as frames arrive |
| Voices | k-means over all onsets | accumulate onset pan and weight; run k-means at the end of the pass |
| Loudness | needs the finished spectrum | falls out of the histogram once the pass completes |
| Session refs | max across all tracks | needs cross-track communication — the canvas plugin owns these and broadcasts them back |

Shapes are unavailable until one pass completes. That is a product change, not
just a technical one: the plugin opens empty and fills in as the song plays.
Neutron and smart:EQ behave the same way, so it is a familiar pattern, but the
first-run experience has to be designed rather than inherited.

**ARA 2** removes the learn pass entirely by giving direct access to the audio and
the timeline. It is the API built for exactly this problem. It is not an option
for the first target: FL Studio does not support it, and neither does Ableton
Live. Treat it as a later accelerator for the hosts that have it, feeding the
same analysis code.

## FL Studio notes

- No ARA 2. The learn pass is mandatory.
- `Vst::ChannelContext::IInfoListener` is not implemented, so track names and
  colours do not arrive from the host. Let the user type a name on the sender,
  and auto-assign "Track 01" otherwise. Do not design around names being free.
- Plugins are not sandboxed or run out-of-process the way Logic and Pro Tools do
  them, so shared memory between sender and canvas should be straightforward
  here. That risk arrives with the macOS build, not this one — but test it before
  committing to the topology, because it can invalidate it.
