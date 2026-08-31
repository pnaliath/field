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
| **Z** — toward you | Depth. Forward is louder, brighter and dry; back is quieter, duller and wetter. |

Overlap is the whole point. Two shapes sitting in the same place means those
tracks share a frequency band *and* a pan position *and* are sounding at the
same time. That is exactly what masking is, and pulling them apart is exactly
the fix.

## What it does

- Drop in stems, or load a demo session that is muddy on purpose
- Drag to pan, drag vertically to tilt, drag the edges for high-pass, low-pass and stereo width
- Push tracks forward and back on the depth rail
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

## Known limits

- Voices are analysis and display only. The audio chain is still one per track,
  so you cannot EQ just the left-hand hi-hat. Splitting the source is out of
  scope here.
- Carve applies a static notch, not dynamic or sidechained EQ.
- Reverb is a single shared convolver, not per-track.

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
