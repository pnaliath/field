# Field 1.0.0-rc.1 — FL Studio native

Windows x64 release candidate. Use one native Field instance on the master. The installer contains the FL-native plugin only. Analysis stays on this computer; Field does not alter, record or export audio.

## Install and open

Close FL Studio, run the installer, and select the FL installation containing FL64.exe. Standard installation locations are detected. Open FL Studio and add **Field 1** to the master. Press play.

The `Field 1 Beta` installation folder and DLL filename are retained to update existing beta installations in place. The visible plugin is Field 1. Do not install a second copy under a different folder. Existing project state versions 1 and 2 load with their camera, visibility and learned profiles; the new frequency range defaults to full range.

Manual installation: copy the `Field 1 Beta` folder from the portable ZIP to `<FL Studio>/Plugins/Fruity/Effects`. Close the host before replacing it. The installer provides a Windows uninstaller; remove that folder to uninstall a manual installation.

## Frequency zoom

The vertical FREQ bar at the right shows the full 28 Hz–18 kHz range.

- Drag its upper handle to set the highest displayed frequency.
- Drag its lower handle to set the lowest displayed frequency.
- Drag the highlighted band to move the selected frequency window.
- Scroll over the bar to zoom around the pointer position.
- Double-click the bar, or click its Reset button, for the full frequency range.

Zoom changes the room's frequency axis and visible geometry only. It does not filter audio or relearn source profiles. The selected range is saved with the project. Camera zoom remains on the mouse wheel over the room.

## Sources and returns

The SOURCES heading switches to ALL ROUTES so every discovered route remains accessible, including silent tracks and collapsed returns. An unverified reverb/delay name is only a classification hint. It cannot erase a source. A return collapses into its source only when a sufficiently confident association exists and the source is visible. An uncertain association produces no guessed particle attachment.

Click a route to inspect it. Use the square to change visibility; Show All / Hide All affect all routes. Right-click a route to set its type or colour. A manual type has priority over native name metadata. Set type to Unknown to allow automatic classification again. Effects visualization can be disabled independently in Settings. Unassigned returns remain visible.

Pan is the current stereo balance. Width measures channel independence separately from gain imbalance. The spectrum defines height and lobes; stereo width affects body width. Louder activity is nearer. Transient positions are held for an event, while sustained sources track live pan. Reverb and delay graphics are conservative relationship estimates, not plugin parameter readouts.

## View and learning

Drag to orbit; scroll over the room to zoom the camera; double-click the room to reset the camera. View provides Perspective, Front, Top and Side. Full screen detaches the canvas; Restore or Esc returns it to the FL editor. The source panel can collapse independently per instance and its preference is saved.

Reset View resets the camera only. The frequency bar has its own reset. Relearn Selected / Relearn All reset analysis independently of view controls. Reset Visual Preferences resets display settings.

## Diagnostics

Settings → Developer diagnostics shows timing. Record diagnostics CSV saves route names, rendered geometry, frequency range and timing metrics, never audio. BUILD.txt identifies the exact source commit. No telemetry or login is required.

## Supported discovery

This product uses the same native input acquisition as the existing Field workflow. It shows the mixer inputs FL exposes to the effect. A child routed exclusively through a subgroup may be visible only as that bus. No per-track Sender workflow is required or installed. Complete hidden-child reconstruction and automatic routing-graph deduplication are not claimed.

## Release status

The candidate is unsigned. Core regressions and an automated Windows UI harness are part of the build. Real FL project acceptance and clean-machine installation results must be recorded before labelling the package a commercially verified final release. The supplied proprietary licence remains in effect.
