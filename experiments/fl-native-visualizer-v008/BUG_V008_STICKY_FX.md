# V0.08 in-DAW regression

Observed in FL Studio: primary visual field can become empty for long periods and show `WAITING TO LEARN THE FIRST PRIMARY AUDIO-BEARING TRACK` even while instruments are playing.

Root cause: V0.08 sticky FX hysteresis retains every previously classified FX link indefinitely and clamps held score to >= 0.40. A false-positive normal source can therefore become permanently hidden as an FX return. Repeated false positives can remove nearly every primary object.

Superseded by V0.09 confidence/hysteresis state with recovery and a non-empty primary safety path.
