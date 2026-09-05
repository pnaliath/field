# Field V1.0 — Production-Ready VST Specification

Field V1.0 ko experiment series ka polished continuation nahi, balki **clean production product** treat karna chahiye.

Core proposition:

**Field is a spatial mix visualizer that turns an entire mix into a live 3D room. Each sound becomes a stable visual object whose position, shape, width, depth, activity, and effects reflect what is actually happening in the mix.**

It is not an EQ, not a spectrum analyser, not a loudness meter, and not an audio processor. It is a **mix understanding tool**.

---

# 1. Product Form

## Plugin formats

V1.0:

- VST3
- Windows 10/11 x64
- Native FL Studio integration where available
- Standard VST3 compatibility layer for other DAWs where technically feasible

Field should eventually support:

- macOS VST3
- AU
- Apple Silicon
- CLAP

But they do not need to block Windows V1.0.

For the first commercial release, **Windows VST3 + best-in-class FL Studio support** is enough.

---

# 2. Core Usage Model

User inserts **one Field instance on the master bus**.

Field receives or discovers the individual mixer sources and reconstructs the visual mix internally.

User does **not** need:

- one plugin instance per track
- manual track pairing
- a separate desktop application
- cloud upload
- account login just to analyse audio
- project export
- audio rendering

Ideal workflow:

1. Install Field.
2. Open DAW.
3. Insert Field.
4. Press play.
5. Field discovers available sources.
6. Room populates.
7. After a few moments, each source develops a stable visual identity.
8. User mixes normally while observing spatial relationships.

---

# 3. Main UI

The plugin window should have three major regions.

## A. 3D Mix Room

Approximately 75–80% of the interface.

Contains the actual visualization.

Room axes:

### X axis — stereo placement

Left ↔ Right.

Derived from:

- pan
- stereo balance
- stereo event locations
- stereo width

### Y axis — frequency

Low frequencies near the floor.

High frequencies toward the top.

Logarithmic scale:

**28 Hz → 18 kHz**

### Z axis — mix depth

Front ↔ Back.

Primarily represents perceived/source level.

Louder sounds move visually forward.

Quieter sounds sit deeper.

This must not continuously swim with microscopic RMS changes.

Depth must be perceptually stable.

---

# 4. Sound Objects

Every source becomes an object.

The object has several independent properties.

## Position

### X

Pan / spatial centre.

### Y

Frequency occupancy is expressed through the shape itself rather than a single Y coordinate.

### Z

Perceived depth / source level.

---

# 5. Spectral Shape

This is Field's central visual language.

A kick should not look like a vocal.

A hi-hat should not look like a bass.

A pad should not look like a flute.

Field learns a stable spectral identity for each source.

Production model:

- 76 logarithmic bands
- 28 Hz–18 kHz
- Hann-window FFT analysis
- percentile-based spectral profile
- leakage suppression
- contiguous lobe construction
- isolated one-band artefacts removed
- small gaps merged
- spectral identity stabilised over time

The object consists of **soft semi-transparent spectral rings/lobes**, not a conventional spectrum curve.

Shape should communicate:

- frequency range
- dominant regions
- gaps
- tonal density
- spectral width

without needing numbers.

---

# 6. Stable Identity vs Live Activity

This separation is critical.

Field must have two different concepts:

## Identity

What this source generally sounds like.

Examples:

- kick spectral shape
- guitar stereo width
- vocal frequency range
- source colour
- persistent stereo topology

Identity changes slowly.

## Activity

What the source is doing right now.

Examples:

- currently sounding
- current transient
- temporary pan movement
- temporary level
- EQ change
- effects tail

Activity changes quickly.

Field must never continuously redefine identity from every audio block.

---

# 7. Source Appearance

Each mixer route gets:

- unique Field colour
- source label
- learned shape
- X location
- width
- depth
- presence
- stereo topology
- optional FX aura

Colours should be highly distinguishable.

Do not depend entirely on DAW mixer colours.

DAW colour may be shown as metadata, but Field's own palette should guarantee readability.

---

# 8. Presence

Objects appear when the source is active.

When source stops:

- object fades naturally
- geometry does not distort
- object does not slide backward
- object does not collapse before disappearing
- source identity remains learned internally

Reappearing sound returns with its identity intact.

---

# 9. Transient Behaviour

Transient sources need event-based visualization.

Examples:

- kick
- snare
- hats
- percussion
- short FX
- plucks

Each transient should create a short-lived **event snapshot**.

Snapshot freezes:

- X
- Z
- source shape
- stereo side

during that event.

The body must not chase the envelope around the room.

Recommended V1 default visual lifetime:

**\~500 ms**

with an adaptive release around source duration.

The 500 ms calibration from experiments can be the starting point, but V1 should make it source-aware rather than universally hard-coded.

---

# 10. Sustained Sources

Examples:

- vocal
- pads
- sustained guitar
- strings
- organ
- long synths

These should behave differently from percussion.

Instead of producing dozens of overlapping snapshots:

- one persistent body
- gradual opacity response
- stable geometry
- live pan movement
- controlled Z changes

Field should classify a source as transient or sustained from envelope behaviour rather than track name.

---

# 11. Stereo Width

Stereo width is independent from pan.

A centred mono source:

- centre position
- narrow object

A centred wide synth:

- centre position
- wide body

A panned stereo source:

- shifted centre
- width preserved

Width should be based on accumulated stereo identity, not one audio block.

Therefore it must not visibly breathe on every frame.

---

# 12. Multiple Spatial Voices

Some tracks contain discrete stereo positions rather than continuous width.

Example:

guitar alternates:

- left
- right
- left
- right

Field should not necessarily render this as one enormous stereo object.

It can identify up to **two stable spatial voices**.

Production V1:

- maximum 2 discrete voices
- persistent L/R topology when confidence is high
- no 1→2→3→1 topology flicker
- voice separation only after sufficient observations

### Sustained dual voice

Two stable bodies.

Example:

double-tracked guitar.

### Transient alternating voice

Only currently active side appears.

Example:

alternating hats.

This distinction should remain.

---

# 13. Pan Movement

Mixer pan changes must be responsive.

Target:

**visible response within one or two UI frames.**

Do not use long-term learned pan for live movement.

Maintain:

- learned spatial identity
- live pan

as separate variables.

---

# 14. Depth / Loudness

Depth is not merely instantaneous RMS.

Production V1 needs a perceptual level estimator using a combination of:

- short-term RMS
- peak
- sustained loudness
- route-relative calibration
- session-relative calibration

Behaviour:

Louder = front.

Quieter = back.

But depth should not wobble with each waveform cycle.

For transients:

**sample depth at event onset/attack and hold it for the event.**

For sustained sources:

use a slow, bounded depth movement.

---

# 15. EQ Change Visualization

Field already explored this and it belongs in V1, but should remain subtle.

Baseline body represents learned source identity.

If EQ changes significantly:

- boosted region slightly expands
- cut region slightly contracts
- temporary highlight can appear

Optional tooltip:

`+4.2 dB @ 2.4 kHz`

But the room should remain understandable without text.

Important:

Normal vocal formants must not be classified as EQ activity.

Therefore require:

- broadband normalization
- temporal persistence
- neighbour-band coherence
- dead zone
- hysteresis

V1 should detect **meaningful sustained spectral change**, not every spectral fluctuation.

---

# 16. Reverb

Reverb should **not appear as another arbitrary source object** when it can confidently be associated with a source.

Visual treatment:

source gets a:

- diffuse halo
- transparent spatial haze
- expanded depth envelope

Amount reflects:

- return contribution
- decay behaviour
- diffusion confidence

Possible semantics:

more reverb = larger/deeper halo.

Dry body remains visible in the middle.

---

# 17. Delay

Delay should appear as temporal spatial repetition.

Potential visual:

- faded repeated contours
- offset echo bodies
- diminishing ghost rings

They remain linked visually to the source.

This is much clearer than showing a delay return as an unrelated mixer object.

---

# 18. FX Detection Safety

Earlier versions proved that this logic must never suppress source rendering aggressively.

Production rule:

**uncertain FX classification can modify visualization, but cannot hide the primary source.**

Only extremely high-confidence return identification may remove a dedicated return body.

Otherwise:

- render source normally
- optionally show FX relationship
- optionally keep return visible

False positive visual clutter is preferable to a missing source.

---

# 19. Group Buses

Group buses are a difficult case.

Examples:

- drum bus
- music bus
- vocal bus
- parallel compressor
- master subgroups

Field must avoid treating every bus as another instrument.

V1 classification categories:

- Source
- FX Return
- Group/Bus
- Unknown

Group buses can appear in a different visual layer.

Recommended V1 behaviour:

### Default

Hide group buses from main room when their content is substantially explained by child sources.

### Sidebar

Still show them.

User can manually enable them.

---

# 20. Parallel Processing

Zero-lag parallel processing should not automatically become reverb/delay.

Examples:

- parallel compression
- saturation bus
- distortion layer

Possible visualization:

small outline/energy layer around original object.

But for V1 this can remain conservative.

Do not over-classify.

---

# 21. Sidebar

Left or right sidebar lists all discovered routes.

Each row:

- colour
- track name
- current activity indicator
- route type
- visibility toggle

Optional icons:

- Source
- Stereo
- Dual
- Bus
- Reverb
- Delay
- Unknown

Clicking a source:

- highlights object
- centres/focuses camera
- opens Inspector

---

# 22. Inspector

Selected source Inspector:

### Identity

- Name
- Route
- Type
- Colour

### Spatial

- Pan
- Width
- Depth
- spatial voices

### Spectrum

- dominant frequency
- low bound
- high bound

### Activity

- peak
- RMS
- presence

### Effects

- Reverb association
- Delay association

These values are secondary.

Field should remain visualization-first.

---

# 23. Camera

Controls:

- drag = orbit
- wheel = zoom
- double-click = reset

Optional:

- Shift + drag = pan camera
- `F` = focus selected source

Camera position must never modify measured source coordinates.

---

# 24. Camera Presets

Useful presets:

- Perspective
- Front
- Top
- Stereo
- Frequency
- Depth

### Front

Best for:

pan + frequency.

### Top

Best for:

pan + depth.

### Side

Best for:

frequency + depth.

---

# 25. Room Grid

Minimal.

Labels:

### Frequency

28 Hz
60 Hz
120 Hz
250 Hz
500 Hz
1 kHz
2 kHz
4 kHz
8 kHz
18 kHz

### Stereo

L
C
R

### Depth

Front
Mid
Back

Grid should never dominate visual objects.

---

# 26. Session Learning

After playback begins:

### Immediate

Presence and basic source position.

### First useful frame

rough spectral object.

### Next few observations

refinement.

### Long-term

stable identity.

User should never wait several seconds for an object to appear.

Target:

**sound onset → visible body ≤ 32 ms** once route discovery exists.

Ideal median:

\~16 ms.

Previous diagnostics already demonstrated that order of response is possible.

---

# 27. Rare / One-Shot Sounds

V1 cannot require 16 FFT frames before showing a crash or single sound effect.

Production solution should combine V0.31 stability with V0.32's useful idea:

**instant provisional body → stable learned body.**

First event:

- sanitized first-frame geometry
- clearly usable immediately

Next few frames:

- rapid refinement

Then:

- slow adaptation

But this should happen without the huge initial `28 Hz–18 kHz` body problem.

---

# 28. Spectral Analysis Architecture

Production architecture should be:

## Audio thread

Only:

- input acquisition
- basic peak/RMS
- pan/balance
- width telemetry
- presence envelope
- transient/onset detection
- copy samples into preallocated analysis transport

Absolutely no:

- large FFT
- allocations
- file I/O
- mutex contention
- expensive classification
- rendering

---

# 29. Analysis Worker

Separate worker thread.

Handles:

- FFT
- spectral profiles
- percentile learner
- voice clustering
- transient classification
- EQ-delta analysis
- FX relationship analysis
- source classification

Uses:

- fixed-capacity buffers
- lock-free queue/ring buffer
- bounded processing
- latest-frame drop strategy if UI/analysis falls behind

For visualizer software:

**dropping stale analysis is better than blocking audio.**

---

# 30. UI Thread

Responsible for:

- render state snapshots
- camera
- GDI+/GPU drawing
- user interaction
- interpolation
- Inspector
- diagnostics UI

No direct complex DSP.

---

# 31. Rendering

V1 should keep the V0.33 improvement:

- real alpha compositing
- anti-aliased geometry
- SourceOver blending
- low-density ring style
- transparent overlapping bodies

However final production renderer should ideally abstract away from Win32 GDI+.

A production path could use:

- JUCE Graphics initially
- Direct2D/Direct3D later
- GPU renderer if necessary

But visual parity matters more than technology choice.

---

# 32. Performance Targets

## Audio callback

Typical:

**<0.1 ms**

Heavy case:

**<10% of smallest practical host buffer budget**

No FFT spikes on audio thread.

## UI

Target:

**60 FPS**

Minimum acceptable under heavy sessions:

**30 FPS**

## Route count

V1 target:

**64 mixer sources**

Should degrade gracefully up to:

**128**

without audio consequences.

---

# 33. Rendering Scalability

With many tracks, do not draw identical detail for everything.

Use LOD.

### Near / selected

full rings + labels + FX.

### Normal

simplified body.

### Far / tiny

few representative rings.

### Inactive

do not render after fade completion.

---

# 34. Label Management

Labels cannot overlap everywhere.

Rules:

- selected source always labelled
- active major sources prioritised
- labels collision-resolved
- fade low-priority labels
- hover reveals hidden name

Avoid 30 floating track names.

---

# 35. Route Discovery

For FL Studio:

native route metadata should provide as much automatic discovery as possible.

Field should know:

- mixer index
- track name
- colour metadata
- audio input
- routing relationships where exposed

No manual configuration for normal FL sessions.

---

# 36. Other DAWs

This is the complicated commercial architecture issue.

A generic VST3 on master normally cannot magically inspect every mixer track independently.

Therefore production Field needs potentially two operating modes.

## Field Native Mode

DAW-specific integration.

Best experience.

FL Studio first.

## Field Link Mode

A lightweight Field Sender plugin inserted on tracks/buses communicates locally with the master Field instance.

Still:

- no cloud
- no audio upload
- no account required

Sender can transmit either:

- analysis features, preferably
- or local audio buffers when required

Commercial product can eventually hide this complexity through DAW-specific workflows.

---

# 37. Privacy

Strong selling point.

Field should be:

**100% local analysis.**

No project audio leaves machine.

No audio stored by default.

No AI cloud processing required.

No training use.

If telemetry exists:

only opt-in anonymous:

- crash
- plugin version
- DAW
- OS
- performance stats

Never audio.

---

# 38. Saving State

DAW project should save:

- camera
- hidden tracks
- source colour overrides
- selected source
- UI preferences
- calibration
- analysis settings

Potentially learned source profiles too.

This is important.

If profile persists with the project, reopening should not require retraining every instrument.

Need fingerprint/revalidation so changed source does not blindly reuse stale identity forever.

---

# 39. Reset Controls

User needs:

### Reset View

Camera only.

### Relearn Selected

Forget selected source identity.

### Relearn All

Forget all session analysis.

### Reset UI

Visual preferences only.

Do not combine everything into one dangerous reset.

---

# 40. Production Settings

Keep settings limited.

## Visual

- Detail: Low / Medium / High
- Labels
- FX visualization
- Room grid
- Animation intensity

## Analysis

- Fast / Balanced / Precise

Internally these can affect:

- FFT cadence
- percentile history
- worker workload

But defaults should work without touching anything.

---

# 41. Diagnostics Mode

Production builds should retain hidden diagnostics.

Toggle through Advanced/Developer mode.

Metrics:

- audio callback ms
- analysis worker ms
- paint ms
- FPS
- active routes
- queue depth
- dropped analysis frames
- onset → visible
- profile ready
- rendered body state
- source type
- pan
- width
- depth
- profile bounds
- FX confidence

Critical improvement over V0.33:

**diagnostics must log the final state actually consumed by renderer.**

Not stale intermediate variables.

---

# 42. CSV Diagnostics

Keep export.

Useful for debugging real user sessions.

CSV should include:

```text
timestamp
route
route_name
route_type
peak_db
rms_db
presence
live_pan
stable_pan
width
depth
voice_count
profile_ready
display_profile_ready
low_hz
high_hz
dominant_hz
onset_count
last_onset_ms
onset_to_visible_ms
reverb_confidence
delay_confidence
audio_callback_ms
analysis_ms
paint_ms
fps
queue_depth
```

`onset_to_visible_ms` must be recorded where actual renderer eligibility occurs.

---

# 43. Crash Safety

A visualizer must never endanger the DAW.

Production rules:

- no exception escapes audio callback
- no allocation failure crashes host
- worker can restart
- malformed metadata ignored
- bad route skipped
- render failure degrades to basic mode
- analysis backlog discarded
- file logging failure ignored safely

---

# 44. Plugin Bypass

Bypass should have zero audible consequence.

Because Field should already be effectively audio-transparent.

The plugin must preserve incoming audio exactly where host architecture requires passthrough.

Automated null testing should verify it.

---

# 45. Audio Integrity

Mandatory tests:

- mono
- stereo
- silence
- 32-bit float
- extreme peaks
- denormals
- 44.1 kHz
- 48 kHz
- 88.2 kHz
- 96 kHz
- 192 kHz if supported
- block sizes 16–4096
- rapidly changing block sizes
- offline rendering
- project stop/start
- seek
- loop
- route addition/removal

Field must never alter audio.

---

# 46. DAW Test Matrix

At minimum V1 Windows QA:

### FL Studio

Primary.

Test:

- latest release
- previous major version

### Ableton Live

VST3 compatibility.

### REAPER

Excellent stress/validation host.

### Cubase

VST3 reference ecosystem.

### Studio One

### Bitwig

But non-FL functionality can initially be clearly labelled if Sender/Link system isn't complete.

---

# 47. Source Test Library

Create reference sessions containing:

- kick
- snare
- hats
- bass
- mono vocal
- stereo vocal
- guitar
- double guitar
- pads
- mono synth
- wide synth
- piano
- strings
- flute
- impacts
- reverb
- delay
- drum bus
- vocal bus
- parallel compression

Every Field release runs against same reference sessions.

---

# 48. Visual Acceptance Tests

These matter as much as unit tests.

Examples:

### Kick

Must appear low.

### Hat

Must appear high.

### Bass

Must not extend to 18 kHz.

### Mono centre vocal

Must be narrow and centred.

### Hard-pan left

Must immediately move left.

### Stereo pad

Should be wider, not become two discrete objects unless data supports that.

### Alternating L/R hat

Must show current side.

### Double-track guitar

Can settle into two stable voices.

### Quieter duplicated source

Should occupy similar frequency shape but sit further back.

### Reverb increase

Should expand/diffuse aura, not create random source disappearance.

---

# 49. Performance Acceptance Tests

Automated stress session:

- 64 routes
- 20 active simultaneously
- several stereo
- multiple reverbs/delays
- 48 kHz
- 64-sample buffer

Pass condition:

- no audible dropouts attributable to Field
- no audio-thread allocation
- analysis may drop frames
- UI remains interactive

---

# 50. UX Principle

The user should not have to understand DSP to understand Field.

Within five seconds, they should visually perceive:

- bass is low
- hat is high
- vocal is centre
- guitar is left
- pad is wide
- louder item is closer
- reverb is surrounding a source

If this isn't immediately obvious, visual mapping failed.

---

# 51. What V1 should NOT have

Avoid scope creep.

No:

- EQ controls
- compression controls
- mix processing
- mastering assistant
- AI mix scoring
- cloud analysis
- automatic mix correction
- presets pretending to “fix” audio
- spectrum tables everywhere
- waveform editor
- recording
- MIDI tools
- collaboration
- DAW replacement features

Field V1 should do one thing:

**make a mix spatially understandable.**

---

# 52. V1 Main Screen

Production screen could contain:

Top bar:

**FIELD**

then:

`View | Reset | Learn | Settings`

Left sidebar:

route list.

Centre:

3D room.

Bottom-right:

camera preset buttons.

Selected source:

compact floating Inspector.

No giant dashboard.

---

# 53. First-Run Experience

First insertion:

Small overlay:

**Play your session. Field will map your mix automatically.**

Then disappear.

No onboarding carousel.

No tutorial wizard.

---

# 54. Commercial V1 Feature List

The store-facing feature list can essentially be:

- Live 3D mix visualization
- Frequency mapped vertically
- Stereo position mapped horizontally
- Loudness mapped into depth
- Learned spectral identities
- Stable transient visualization
- Stereo width visualization
- Dual spatial voice detection
- Reverb visualization
- Delay visualization
- Live pan tracking
- Spectral change visualization
- Interactive 3D camera
- Automatic FL Studio route discovery
- Local-only analysis
- Session profile persistence
- 60 FPS rendering
- Diagnostics export

---

# 55. V1 Architecture Summary

```text
DAW / FL Studio
      │
      ▼
Native Route Acquisition
      │
      ├── Audio passthrough
      │
      ├── Fast telemetry
      │      Peak
      │      RMS
      │      Pan
      │      Width
      │      Onsets
      │      Presence
      │
      ▼
Lock-Free Analysis Transport
      │
      ▼
Analysis Worker
      │
      ├── FFT
      ├── Spectral identity
      ├── Source behaviour
      ├── Stereo voices
      ├── EQ delta
      ├── FX relationships
      └── Stable spatial state
              │
              ▼
       Immutable Render Snapshot
              │
              ▼
          UI Renderer
              │
              ├── 3D room
              ├── bodies
              ├── FX
              ├── labels
              └── inspector
```

---

# 56. V0.33 → V1.0 Development Priorities

Current V0.33 se directly V1 polish karna wrong hoga. Production sequence should roughly be:

| StageObjective |                                                                                   |
| -------------- | --------------------------------------------------------------------------------- |
| **V0.34**      | Fix diagnostics so final render state is measurable                               |
| **V0.35**      | Move expensive spectral analysis completely off audio thread                      |
| **V0.36**      | Unify V0.31 stable behaviour with selected V0.32 instant-first-shape improvements |
| **V0.37**      | Final transient/sustained state machine                                           |
| **V0.38**      | Production spectral identity model                                                |
| **V0.39**      | Production stereo / dual-voice model                                              |
| **V0.40**      | Safe FX association without body suppression                                      |
| **V0.41**      | Bus / return classification                                                       |
| **V0.42**      | Persistent project state / relearning                                             |
| **V0.43**      | Renderer performance + LOD                                                        |
| **V0.44**      | UI/Inspector/route sidebar production pass                                        |
| **V0.45**      | 64-route stress testing                                                           |
| **V0.46**      | Audio integrity + host lifecycle tests                                            |
| **V0.47**      | Installer / signing / plugin discovery                                            |
| **V0.48**      | External beta                                                                     |
| **V0.49**      | Release candidate                                                                 |
| **V1.0**       | Commercial production build                                                       |

Version numbers themselves aren't important. The gates are.

---

# 57. Definition of “Production Ready”

Field is **not V1.0** merely because all desired visuals work.

V1.0 only when all of these are true:

**Functional**

- every legitimate active route consistently appears
- transient/sustained behaviour predictable
- pan correct
- frequency geometry plausible
- depth stable
- width stable
- FX association cannot erase source
- rare sounds appear immediately

**Real-time**

- no FFT on audio thread
- no audio-thread allocations
- no blocking locks
- bounded CPU
- analysis backlog disposable

**Visual**

- 3D grammar understandable
- no body swimming
- no giant first-frame blob
- no random topology switching
- no alpha/render mismatch
- labels manageable

**Persistence**

- project reopens correctly
- source profiles persist where appropriate
- reset/relearn works

**Compatibility**

- clean install/uninstall
- host rescans reliably
- plugin state survives project save/load
- common sample rates/block sizes tested

**Safety**

- no audio modification
- no host crashes
- no audio dropout caused by analysis
- corrupt diagnostics cannot affect DSP

**Observability**

- final renderer state measurable
- support diagnostics exportable
- crashes diagnosable

That is the actual Field V1.0 target: **a stable professional mix-visualization instrument, not an experimental spectrum renderer wrapped in a plugin.**