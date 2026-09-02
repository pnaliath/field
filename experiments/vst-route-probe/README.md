# Field Route Probe

A deliberately empty, audio-transparent VST3 used to test exactly how much track/routing metadata a DAW exposes to a plug-in instance.

## What it probes

The plug-in implements the raw VST3 `ChannelContext::IInfoListener` interface and displays the following as read-only parameters in the host's generic plug-in editor:

- Current channel name
- Every distinct channel name ever received by this instance
- Number of channel-context callbacks received
- Channel UID
- Channel runtime ID
- Channel index
- Channel index namespace
- Plug-in location (pre/post fader/panner when supplied)
- Channel colour
- A routing-probe status line

It does **not** alter audio.

## The experiment

1. In a DAW, create tracks `Kick`, `Bass`, and `Vocal`.
2. Route all three into a group/bus called `MIX BUS`.
3. Put **only one** `Field Route Probe` instance on `MIX BUS`.
4. Open the plug-in. If the DAW does not automatically show a UI, switch to its generic parameter view.
5. Inspect **Current channel** and **All names observed**.
6. Rename source tracks and change routing while the probe remains open.
7. Move/copy the probe to the master output and repeat.

### Result interpretation

- If `All names observed` contains `Kick | Bass | Vocal | MIX BUS`, the host is exposing more routing context than standard VST3 requires and that host may support a master-only Field integration through a host-specific path.
- If it contains only `MIX BUS`, the host is behaving as expected: the VST3 instance receives metadata for the channel on which it is instantiated, but not the upstream routing graph.
- If no channel name appears at all, that host is not supplying optional VST3 channel-context information to this plug-in.

## Why this test exists

VST3's standard channel-context interface is documented as describing the channel where the plug-in instance lives. There is no standard VST3 call for enumerating all DAW tracks routed into that channel. This probe is intended to verify real host behaviour rather than relying only on the specification.

## Build on Windows

The repository includes a GitHub Actions workflow that builds an x64 Windows VST3. For a local build:

```powershell
cmake -S experiments/vst-route-probe -B build/route-probe -G "Visual Studio 17 2022" -A x64
cmake --build build/route-probe --config Release --target FieldRouteProbe
```

The build fetches the Steinberg VST3 SDK automatically.
