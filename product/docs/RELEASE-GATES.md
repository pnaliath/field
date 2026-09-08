# Field FL-native release assessment — RC.1

Baseline: fix/beta1-product-issues at 13d22b4. Development: release/v1.0-product.

## Scope agreed 2026-09-08

Ship the existing single-instance FL-native architecture. Per-track Senders and the VST3 compatibility experiment are excluded from the released build and installer. Hidden subgroup children remain subject to the audio routes actually exposed by FL; the product does not promise reconstructed inaccessible tracks.

## Implemented and covered by regression tests

- Audio passthrough stays separate from analysis; no FFT or allocation in core capture.
- Short first events receive provisional shapes without waiting for later sounds.
- Sustained geometry uses live pan; mono channel imbalance does not imply stereo width.
- Manual route types survive native metadata refresh and project save/load.
- Names alone cannot remove bodies. Unassociated returns remain inspectable; no best-guess fallback FX attachment.
- Stereo width independently changes body geometry.
- Draggable vertical frequency range, range pan, pointer-centred wheel zoom and reset; version-3 state persistence.
- UI state is per instance, including sidebar collapse. Versions 1 and 2 remain readable.
- The native DLL harness exercises the exported factory, actual callback passthrough, variable blocks/rates, offline/flush, route churn, IStream save/restore, corrupt state, editor reopen, multiple instances and destruction while fullscreen. This is a simulated SDK host, not a substitute for FL acceptance.
- The Windows UI harness exercises actual rendering, source visibility, range controls, state restoration, fullscreen restoration and camera dragging. PNG generation alone is no longer the acceptance criterion.

## Gates requiring actual host evidence

- Current and previous supported FL major: master passthrough/null, stop/start, seek/loop, route add/remove/reorder, project save/reopen, editor close/reopen and plugin removal.
- FL-native SDK callback acquisition timing at 64-sample buffers with 64 routes / 20 active, and graceful 128-route behaviour. Core capture tests do not substitute for this.
- Renderer frame time and onset-to-visible distribution in real musical projects. The worker/UI snapshot mutex remains; measured host responsiveness determines further optimization.
- Reference music for transient/sustained classification, simultaneous stereo sources, spectral-change/formant discrimination and return association precision.
- Clean-machine install/upgrade/uninstall/rescan, signing and FL SDK redistribution provenance.

No evidence for these host gates is invented by the build. See BUILD.txt and the attached validation log for the exact compiled candidate. The package remains a release candidate until host acceptance is recorded.
