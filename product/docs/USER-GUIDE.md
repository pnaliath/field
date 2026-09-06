# Field 1.0.0-beta.1 Demo

**Proprietary commercial software — evaluation only.** This is a pre-release demo build of Field. It may be installed and used only for personal or internal evaluation and testing. It may not be sold, resold, shared, uploaded, redistributed, mirrored, bundled, repackaged, sublicensed, rented, leased, lent, or otherwise provided to another person without prior written permission from Field. See `FIELD-DEMO-LICENSE.txt` / the installer license for the complete terms.

Windows x64 beta candidate. A spatial mix visualizer. Audio passes through unchanged. No account, network, cloud analysis, recording, or audio export.

## Install

Close FL Studio and run the setup EXE. The installer identifies this build as **Field 1.0 Beta Demo**, requires acceptance of the Field Commercial Demo / Evaluation License, and installs **only the FL Studio native one-instance plugin**. There is no VST3 component-selection page in the installer. Select the actual FL Studio installation containing `FL64.exe`, then rescan/restart FL Studio if needed.

Manual installation from the ZIP:

- For the supported FL Studio demo workflow, copy the `Field 1 Beta` folder to `<FL Studio installation>\Plugins\Fruity\Effects`.
- The portable package may also contain development/compatibility VST3 binaries used by the build and validation pipeline. They are not installed by the demo installer and are not the intended FL one-instance workflow.
- Remove the native folder to uninstall a manual installation. The installer has a normal Windows uninstaller.

The ZIP is also evaluation-only. Manual installation does not grant redistribution or resale rights.

## FL Studio — native one-instance mode

For FL Studio, **use the native Field plugin as the primary mode**. Insert **Field 1.0 Beta** on the master and press play. One native Field instance queries FL's exposed mixer input names and read-only route buffers. It copies the authoritative master input to its output; it never substitutes a reconstructed sum. Analysis starts automatically.

Only routes the host exposes to this native effect can be discovered. A child track routed solely through a subgroup may not be exposed separately. Field cannot inspect arbitrary hidden child routes or reconstruct a routing graph that the SDK does not provide. Put it at the relevant bus to inspect that bus's exposed inputs. It cannot promise a complete independent object for every mixer channel in every FL project.

Do not use the VST3 master instance as FL Studio's one-instance whole-mixer mode. A normal VST3 insert receives only its own host audio input and therefore cannot automatically inspect every unrelated mixer track.

## VST3 Link — development compatibility mode

The repository/package can still build the generic VST3 + Sender path for validation and future compatibility work, but the demo installer does not install it. The commercial FL workflow for this beta is Native one-instance mode.

## Read the room

Left/right is stereo balance. Height is frequency from 28 Hz to 18 kHz. Louder sources are closer. Width is learned separately from pan. Transients freeze their position during their fade; sustained sources use a persistent body. Spectral shapes learn during playback and are preserved with project state, then revalidated against new audio.

The sidebar lists audible source objects, not dedicated auxiliary FX returns. Common named `REV`/`REVERB`, `DEL`/`DELAY`/`ECHO`, and exact `EQ` utility routes are kept out of the independent source-body list. Reverb/delay returns continue to be analysed so they can contribute source-associated effect visuals when a reliable relationship exists.

Use **Show All** and **Hide All** above the source list to enable or disable all source visuals at once. The per-source square still controls individual visibility. Click a source to inspect it. The inspector has an `×` control to close it. Right-click a source to choose its route type or colour. Scroll the sidebar to see further sources. Route type overrides do not change audio.

Drag the room to orbit, wheel to zoom, and double-click to reset the view. Use **Full screen** in the upper-right to detach the Field canvas to the current monitor; use **Restore** or `Esc` to return it to the host editor. The View menu has Perspective, Front, Top, and Side views. Reset View affects only the camera. Reset visual preferences affects the display. Learn has independent selected/all relearn actions.

Settings controls labels, grid, FX, render detail, analysis cadence, and developer diagnostics. CSV recording is explicit: choose Record diagnostics CSV and a destination; stop from the same menu. Logs contain route names and metrics, never audio. Treat route names as project metadata when sharing logs.

## Licensing and third-party notices

Field itself is proprietary commercial software. This demo grants evaluation rights only; it does not grant rights to sell, redistribute, share, publish, sublicense, mirror, bundle, repackage, or commercially exploit Field.

Third-party license files included in the package apply only to the specifically identified third-party components. They do **not** grant permission to redistribute, sell, sublicense, repackage, or otherwise distribute Field itself.

## Current limits

This is an unsigned pre-release demo. External DAW testing, installation testing and measured release thresholds remain open; see RELEASE-GATES.md. Do not rename it final V1.0 based on a successful compiler or VST3 validator run.
