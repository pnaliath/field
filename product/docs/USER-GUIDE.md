# Field 1.0.0-beta.1

Windows x64 beta candidate. A spatial mix visualizer. Audio passes through unchanged. No account, network, cloud analysis, recording, or audio export.

## Install

Close the DAW. Run the setup EXE. Select VST3 and/or FL native. For FL native, select the actual FL Studio installation containing FL64.exe. Rescan plugins after installation.

Manual installation from the ZIP:

- Copy `FieldVST3.vst3` to `C:\Program Files\Common Files\VST3`. The bundle contains both **Field 1.0 Beta** and **Field Sender 1.0 Beta**.
- Copy the `Field 1 Beta` folder to `<FL Studio installation>\Plugins\Fruity\Effects`.
- Remove these same folders to uninstall a manual installation. The installer has a normal Windows uninstaller.

## FL native

Insert **Field 1.0 Beta** on the master and press play. Field queries FL's native input names and read-only route buffers. It copies the authoritative master input to its output; it never substitutes a reconstructed sum. Analysis starts automatically.

Only routes the host exposes to this effect can be discovered. A child track routed solely through a subgroup may not be exposed separately. Field cannot inspect arbitrary hidden child routes or reconstruct a routing graph that the SDK does not provide. Put it at the relevant bus to inspect that bus's exposed inputs. It cannot promise a complete independent object for every mixer channel in every FL project.

## VST3 Link

Insert **Field 1.0 Beta** on the master. Its upper right corner shows `Link session N`. Insert **Field Sender 1.0 Beta** on each source you want to see, select that session number, and enter the source name. Sender starts disconnected to prevent accidental mixing of projects. Audio passes through Sender unchanged. Master-only VST3 insertion shows one aggregate Master body until Senders are connected.

There are 16 explicit local Link sessions and up to 127 Sender sources per session. Keep simultaneous projects on different session numbers. This beta supports instances loaded in the same host process from the same VST3 module; hosts that bridge or isolate plugins into separate processes are unsupported. Saved session numbers are restored; verify numbers when duplicating or simultaneously opening projects. Sender needs an editor visit to choose its session; this is not automatic whole-project discovery.

## Read the room

Left/right is stereo balance. Height is frequency from 28 Hz to 18 kHz. Louder sources are closer. Width is learned separately from pan. Transients freeze their position during their fade; sustained sources use a persistent body. Spectral shapes learn during playback and are preserved with project state, then revalidated against new audio.

Click a sidebar source to select it. The checkbox controls visibility. Right-click a sidebar source to choose its route type or colour. Scroll the sidebar to see further sources. Route type overrides do not change audio. FX associations add an aura or echo outline and never hide source bodies. Association and spectral-change indicators are conservative heuristics, not measured plugin EQ settings or guaranteed effect detection.

Drag the room to orbit, wheel to zoom, and double-click to reset the view. The View menu has Perspective, Front, Top, and Side views. Reset View affects only the camera. Reset visual preferences affects the display. Learn has independent selected/all relearn actions.

Settings controls labels, grid, FX, render detail, analysis cadence, and developer diagnostics. CSV recording is explicit: choose Record diagnostics CSV and a destination; stop from the same menu. Logs contain route names and metrics, never audio. Treat route names as project metadata when sharing logs.

## Current limits

This is an unsigned beta. External DAW testing, installation testing and measured release thresholds remain open; see RELEASE-GATES.md. Do not rename it final V1.0 based on a successful compiler or VST3 validator run.
