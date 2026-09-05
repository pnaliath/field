# V1.0 release assessment

Baseline inspected: `pnaliath/field`, V0.33 branch `experiment/fl-native-visualizer-v0.33-web-render-parity`, commit `60054c71af508563a0d2c04a3ac31b477d602cfe` (2026-09-05). User specification: all 57 sections in V1-SPECIFICATION.md.

## Why the baseline was not a final product

- V0.33 compiled an FL-native DLL, not a VST3. The root README still described the original browser processing prototype.
- Source generation recursively depended on V0.04 through V0.31 plus multiple repair wrappers. Product logic was not an independent maintained target.
- `Eff_Render` ran the 4096-point FFT, histogram learner and spatial clustering.
- Active mode copied a sum of the discovered routes to the output; that sum was not the authoritative master signal. Bypass and Null Check were experimental audio modes.
- `drawSpectralBody` had been replaced without restoring its first-draw diagnostic stamp; final display bounds and actual depth were not the values consistently reported in CSV.
- The display learner required sixteen FFT observations. Project state was not persisted by the visualizer.

## Implemented candidate

A separate `product/` C++17 target uses shared analysis/UI code for the FL native plugin and a VST3 bundle containing Field and Field Sender. Experiments remain intact. No JUCE dependency was introduced.

- Authoritative input passthrough for FL native; float32/float64 mono/stereo passthrough for VST3.
- Preallocated SPSC stereo sample transport; bounded producer/drop behaviour. FFT and percentile learning on a separate worker.
- 76 log bands, Hann FFT, both-channel energy so anti-phase stereo cannot vanish, first-window provisional shape, percentile identity and lobe cleanup.
- Live pan, stable width, level-derived bounded depth, transient event hold/fade, envelope-based sustained classification, maximum two learned event pan anchors.
- Conservative positive-lag spectral/envelope FX association. No automatic source suppression.
- Real GDI+ alpha, ring geometry, detail reduction, label collision limit, camera views, source list, visibility, type/colour overrides, Inspector and explicit diagnostics CSV.
- Versioned project state with checksum, finite/range validation, size bounds, profile revalidation and separate reset/relearn controls.
- Windows native DLL and VST3 build targets, VST3 SDK validator, executable core tests, actual renderer capture harness, ZIP and Inno Setup installer.

## Release gates still open

The attached specification explicitly defines V1.0 by verified behaviour, performance, compatibility and safety. A successful build cannot close these gates.

| Requirement | Candidate status / remaining work |
| --- | --- |
| All independent FL mixer sources from one master instance | Only exposed direct native inputs are supported. Hidden subgroup children and complete routing relationships are not available through this implementation. Validate host behaviour and define truthful scope. |
| Generic DAW operation | Same-process VST3 Link implemented. Bridged/out-of-process linking and simultaneous project isolation need a stronger transport/session design. |
| Stable transient/sustained classification | Heuristic implemented. Must test vocal gaps, long percussion decays, repeated notes and sparse one-shots on reference music. |
| Dual sustained stereo voices | Two event-derived pan anchors implemented; independent simultaneous double-track analysis and common live pan shift are not fully implemented. |
| Perceptual/session-relative depth | RMS/peak blend plus bounded smoothing implemented. Route-relative/session-relative loudness calibration is not yet implemented. |
| Meaningful EQ change | Broadband-normalized persistent neighbour-coherent spectral changes implemented. Vocal-formant false positive acceptance is unverified. |
| Reverb/delay | Positive-lag relationship heuristic and linked graphics implemented. Tail/diffusion-specific detection is incomplete; explicit route type helps. No source is hidden. |
| Group/bus deduplication | Manual route types and visibility implemented. Automatic explained-by-children graph classification is not implemented. |
| Immutable render state | Renderer consumes a copied snapshot. Worker and GUI use a mutex; the audio callback never acquires it. This is not the requested lock-free immutable snapshot handoff. |
| Rare event onset to visible <=32 ms | Provisional path exists. Real renderer stamps metrics. Must measure distribution at each supported sample rate/buffer in FL. |
| 60 FPS / >=30 FPS heavy | LOD exists; real Windows host sessions at 64/128 routes remain unmeasured. |
| Audio callback typical <0.1 ms / heavy <10% buffer | Local synthetic capture result is not a host timing guarantee. Native SDK acquisition and all supported DAWs require profiling. |
| Session and lifecycle safety | Core state tests run; full project reopen, seek, looping, route churn, UI reopen and plugin removal tests in real hosts remain open. |
| Commercial installer/signing | Installer target exists; code signing and clean-machine install/uninstall/rescan QA remain open. FL SDK provenance/distribution review remains open. |
| Reference sessions / external beta | No supplied reproducible FL reference project or DAW installation is available in this workspace. FL current/previous major, REAPER, Live, Cubase, Studio One and Bitwig QA have not been performed. |

Final V1.0 is blocked until these required implementation gaps and host acceptance gates are resolved. This package is explicitly `1.0.0-beta.1`.
