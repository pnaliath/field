# Field

A browser prototype for mixing by moving shapes instead of numbers.

Every track is drawn on a single canvas where **position, size and form are its
actual pan, level and frequency content** — and where two shapes overlapping
means those tracks are masking each other.

**[Try it →](https://YOURNAME.github.io/field/)**

---

## The axes

| Axis | Meaning |
|---|---|
| **X** — across | Pan |
| **Y** — up | Frequency, log scale. A shape covers only the range the track really occupies. |
| **Z** — toward you | Depth. Forward is louder and brighter, back is quieter and duller. Reverb is a separate control. |

Overlap is the whole point. Two shapes sitting in the same place means those
tracks share a frequency band *and* a pan position *and* are sounding at the
same time. That is exactly what masking is, and pulling them apart is exactly
the fix.

## What it does

- Drop in stems, or load a demo session that is muddy on purpose
- Drag to pan, drag vertically to tilt, drag the edges for high-pass, low-pass and stereo width
- Push tracks forward and back on the depth rail, and set reverb on its own rail
- Sculpt into a shape with a knife tool; the curve you draw is fitted to real filters
- See masking as orange bands, with a one-click carve on the lower-priority track
- Export the result as a WAV

No build step, no dependencies. One HTML file, Web Audio API throughout.

## How the shapes are made

Everything is measured once, offline, when a file loads. Nothing animates with
the waveform — a shape only changes when *you* change it.

1. **Spectrum.** A long-term spectrum per track, taken as the 82nd percentile of
   each log band across the whole file. Percentile rather than mean, so a hi-hat
   that only sounds on eighths still reads as bright instead of averaging away.
2. **Voices.** Onsets are detected and each one's position in the stereo field is
   measured from its L/R energy. Those positions are clustered, and if they
   genuinely separate, the track is split into several shapes — a hi-hat that
   alternates left and right becomes two blobs that trade off.
3. **Envelope.** A 100 Hz amplitude envelope per voice decides when its shape is
   lit. Shapes fade in as their sound arrives and out as it decays.
4. **EQ.** Filter curves are read back analytically from unconnected biquads, so
   the outline bends the moment you move a control, whether or not audio is
   playing.
5. **Depth.** The Z axis is K-weighted loudness, weighted by how much of the
   loop a part actually occupies — not peak level, which comes out nearly
   identical for every track.

Masking is computed between voices rather than tracks, and weighted by how often
the two actually sound at the same time. Two parts that never coincide do not
mask each other, however much they overlap on screen.

## Status

This is Phase 0. It exists to answer one question before a single line of C++
gets written:

> **Can someone reshape a blob and correctly predict what will happen to the sound?**

If the answer is no, the shape grammar is wrong and the plugin should not be
built. Everything else — VST3, JUCE, shared memory, cross-DAW QA — is downstream
of that.

### Kill criteria

- 5 test users, 10 minutes each. Kill if 3 or more cannot predict what a reshape gesture will do.
- 1,000 visitors. Kill if under 5% upload stems, or under 1% export a finished mix.

## Honest about what the numbers are

The masking display is a **UX heuristic, not an acoustic measurement**. It
combines spectral overlap, pan overlap, co-occurrence in time, relative
loudness and depth separation into one severity figure. Pan is inferred from
L/R energy, which ignores phase, correlation and precedence effects. Loudness
uses an approximation of K-weighting, at reduced strength. It is meant to
point at places worth listening to. It is not a masking detector.

## Two variants, deliberately

The **Room** view puts the field in perspective; **Flat** keeps depth as size
alone. The 3D room looks better, which is not the same as reading better — a
shape can appear narrower because the camera turned rather than because its
audio changed. Both ship so the question can be settled by testing.

## Known limits

- Voices are analysis and display only. The audio chain is still one per track,
  so you cannot EQ just the left-hand hi-hat. Splitting the source is out of
  scope here.
- Carve applies static notches (up to four per track), not dynamic or sidechained EQ.
- Reverb is a single shared convolver with per-track sends, not per-track units.
- Analysis runs on the main thread, so a large session will pause while it loads.
- Collision analysis recomputes every frame; fine for a handful of stems, not for forty.
- The renderer is Canvas2D. It is not built for a big session yet.

## Running locally

Open `index.html` in a browser. That is the whole procedure.

Some browsers restrict the Web Audio API on `file://` URLs. If audio does not
start, serve it instead:

```
python3 -m http.server 8000
```

then visit `http://localhost:8000`.

## Licence

MIT. See [LICENSE](LICENSE).
