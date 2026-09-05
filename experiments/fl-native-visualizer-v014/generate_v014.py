from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v013_dir = root / "fl-native-visualizer-v013"

runpy.run_path(str(v013_dir / "generate_v013.py"), run_name="__main__")
src = v013_dir / "generated" / "fieldv013.cpp"
out = here / "generated" / "fieldv014.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.14 could not find patch point: {label}")
    text = text.replace(old, new, 1)


# Fresh identity.
text = text.replace("Field V0.13 Stable Depth + Axis Controls", "Field V0.14 Stable Pose + Quiet Tracks")
text = text.replace("FieldV013", "FieldV014")
text = text.replace("V0.13", "V0.14")
text = text.replace("V013", "V014")

# -----------------------------------------------------------------------------
# 1) Invert controls are CAMERA-DRAG direction controls only.
# Room semantics remain fixed: X is pan, Y is frequency. Do not mirror markings/data.
replace_once(
    "        const float displayT = invertY ? (1.0f - t) : t;\n        return 0.06f + displayT * 0.96f;",
    "        return 0.06f + t * 0.96f;",
    "restore fixed frequency axis semantics",
)
replace_once(
    "        const float X = invertX ? -wx : wx;",
    "        const float X = wx;",
    "restore fixed pan axis semantics",
)
replace_once(
    "                    self->orbitYaw += static_cast<float> (dx) * 0.0080f;\n"
    "                    self->orbitPitch = std::clamp (self->orbitPitch + static_cast<float> (dy) * 0.0060f, -1.10f, 1.10f);",
    "                    const float dragX = self->invertX ? -static_cast<float> (dx) : static_cast<float> (dx);\n"
    "                    const float dragY = self->invertY ? -static_cast<float> (dy) : static_cast<float> (dy);\n"
    "                    self->orbitYaw += dragX * 0.0080f;\n"
    "                    self->orbitPitch = std::clamp (self->orbitPitch + dragY * 0.0060f, -1.10f, 1.10f);",
    "mouse orbit direction inversion",
)
text = text.replace('L"Invert X"', 'L"Invert drag X"')
text = text.replace('L"Invert Y"', 'L"Invert drag Y"')

# -----------------------------------------------------------------------------
# 2) Field-owned high-separation palette. FL colours are metadata, not display identity.
field_palette = r'''
COLORREF fieldRouteColor (const InputMetadata& meta)
{
    static constexpr std::array<COLORREF, 24> palette {
        RGB (236,  72, 153), RGB ( 34, 211, 238), RGB (250, 204,  21), RGB ( 74, 222, 128),
        RGB (168,  85, 247), RGB (249, 115,  22), RGB ( 59, 130, 246), RGB (244,  63,  94),
        RGB ( 20, 184, 166), RGB (217,  70, 239), RGB (163, 230,  53), RGB (251, 146,  60),
        RGB ( 14, 165, 233), RGB (232, 121, 249), RGB (132, 204,  22), RGB (248, 113, 113),
        RGB ( 45, 212, 191), RGB (129, 140, 248), RGB (234, 179,   8), RGB (244, 114, 182),
        RGB ( 96, 165, 250), RGB ( 52, 211, 153), RGB (192, 132, 252), RGB (251, 191,  36)
    };
    const int key = meta.mixerIndex >= 0 ? meta.mixerIndex : meta.routeIndex;
    const size_t index = static_cast<size_t> (std::abs (key)) % palette.size ();
    return palette[index];
}

'''
replace_once(
    "void analyseStereo (PWAV32FS buffer, int length, float& rmsDb, float& peakDb)\n{",
    field_palette + "void analyseStereo (PWAV32FS buffer, int length, float& rmsDb, float& peakDb)\n{",
    "Field palette helper",
)
text = text.replace(
    "enhanceMixerColor (static_cast<COLORREF> (track.meta->color & 0x00FFFFFF))",
    "fieldRouteColor (*track.meta)"
)
text = text.replace(
    "enhanceMixerColor (static_cast<COLORREF> (item.color & 0x00FFFFFF))",
    "fieldRouteColor (item)"
)

# -----------------------------------------------------------------------------
# 3) Distinguish live signal from learned existence. A zero-filled buffer must not reset
# pan/width or allow silence to alter the latched Z topology class.
replace_once(
    "        for (auto& flag : everActive)\n            flag.store (false, std::memory_order_relaxed);",
    "        for (auto& flag : everActive)\n            flag.store (false, std::memory_order_relaxed);\n"
    "        for (auto& flag : routeHasSignal)\n            flag.store (false, std::memory_order_relaxed);",
    "route signal-state initialization",
)
replace_once(
    "    std::array<std::atomic<bool>, kMaxRoutes> everActive;\n",
    "    std::array<std::atomic<bool>, kMaxRoutes> everActive;\n"
    "    std::array<std::atomic<bool>, kMaxRoutes> routeHasSignal;\n",
    "route signal-state member",
)

# Every block begins inactive; only real non-zero signal sets this route live.
replace_once(
    "            peakCell.store (oldPeak + (-120.0f - oldPeak) * 0.008f, std::memory_order_relaxed);\n        }",
    "            peakCell.store (oldPeak + (-120.0f - oldPeak) * 0.008f, std::memory_order_relaxed);\n"
    "            routeHasSignal[static_cast<size_t> (route)].store (false, std::memory_order_relaxed);\n"
    "        }",
    "reset current-signal flags",
)

# Much lower existence floor. -120 dB is the hard numerical zero in this probe, so -114 dB
# still rejects true zero while retaining legitimately quiet routed material.
replace_once(
    "            historyFrame[routeArrayIndex] = clamp01 ((targetPeakDb + 84.0f) / 60.0f);\n"
    "            if (targetPeakDb > -96.0f)\n"
    "                everActive[routeArrayIndex].store (true, std::memory_order_relaxed);",
    "            const bool hasSignal = targetPeakDb > -114.0f;\n"
    "            historyFrame[routeArrayIndex] = clamp01 ((targetPeakDb + 114.0f) / 90.0f);\n"
    "            routeHasSignal[routeArrayIndex].store (hasSignal, std::memory_order_relaxed);\n"
    "            if (hasSignal)\n"
    "                everActive[routeArrayIndex].store (true, std::memory_order_relaxed);",
    "quiet route learning floor",
)

# Keep peak meter decay, but only update spatial pose/spectrum when real signal exists.
pose_block = (
    "            auto& balanceCell = routeBalance[routeArrayIndex];\n"
    "            const float oldBalance = balanceCell.load (std::memory_order_relaxed);\n"
    "            balanceCell.store (oldBalance + (balance - oldBalance) * 0.035f, std::memory_order_relaxed);\n\n"
    "            auto& widthCell = routeWidth[routeArrayIndex];\n"
    "            const float oldWidth = widthCell.load (std::memory_order_relaxed);\n"
    "            widthCell.store (oldWidth + (width - oldWidth) * 0.035f, std::memory_order_relaxed);\n"
    "            if (doSpectrum)\n"
    "                analyseSpectrum (routeArrayIndex, routeBuffer, length);"
)
pose_replacement = (
    "            if (hasSignal)\n"
    "            {\n"
    "                auto& balanceCell = routeBalance[routeArrayIndex];\n"
    "                const float oldBalance = balanceCell.load (std::memory_order_relaxed);\n"
    "                balanceCell.store (oldBalance + (balance - oldBalance) * 0.035f, std::memory_order_relaxed);\n\n"
    "                auto& widthCell = routeWidth[routeArrayIndex];\n"
    "                const float oldWidth = widthCell.load (std::memory_order_relaxed);\n"
    "                widthCell.store (oldWidth + (width - oldWidth) * 0.035f, std::memory_order_relaxed);\n"
    "                if (doSpectrum)\n"
    "                    analyseSpectrum (routeArrayIndex, routeBuffer, length);\n"
    "            }"
)
replace_once(pose_block, pose_replacement, "hold last meaningful pose on silence")

# Quiet tracks still need a visible spectral body. Extend the spectral analysis floor substantially.
replace_once(
    "            const float normalized = clamp01 ((db + 72.0f) / 72.0f);",
    "            const float normalized = clamp01 ((db + 116.0f) / 104.0f);",
    "quiet spectrum normalization",
)

# Silence cannot collapse a wet/deep source back to the dry/front depth class.
replace_once(
    "            const unsigned char observedClass = static_cast<unsigned char> (\n"
    "                (reverbAmount > 0.015f ? 1 : 0) | (delayAmount > 0.015f ? 2 : 0));",
    "            const bool hasCurrentSignal = routeHasSignal[idx].load (std::memory_order_relaxed);\n"
    "            const unsigned char observedClass = static_cast<unsigned char> (\n"
    "                (reverbAmount > 0.015f ? 1 : 0) | (delayAmount > 0.015f ? 2 : 0));",
    "Z live-signal gate",
)
replace_once(
    "            else if (observedClass != spatialDepthClass[idx])",
    "            else if (hasCurrentSignal && observedClass != spatialDepthClass[idx])",
    "silence cannot change Z class",
)

# Fade silent learned objects in place instead of making a bright frozen body. Quiet active tracks
# remain visible because the presence curve begins at the new -114 dB floor.
replace_once(
    "        const COLORREF frontFill = mixColor (raw, bg, 0.58f);\n"
    "        const COLORREF backFill = mixColor (raw, bg, 0.78f);\n"
    "        const COLORREF sideFill = mixColor (raw, bg, 0.70f);\n"
    "        const COLORREF outline = mixColor (raw, RGB (242, 248, 255), 0.22f);",
    "        const float presence = clamp01 ((track.peakDb + 114.0f) / 78.0f);\n"
    "        const COLORREF frontFill = mixColor (raw, bg, 0.82f - presence * 0.26f);\n"
    "        const COLORREF backFill = mixColor (raw, bg, 0.91f - presence * 0.13f);\n"
    "        const COLORREF sideFill = mixColor (raw, bg, 0.88f - presence * 0.18f);\n"
    "        const COLORREF brightOutline = mixColor (raw, RGB (242, 248, 255), 0.18f);\n"
    "        const COLORREF outline = mixColor (brightOutline, bg, (1.0f - presence) * 0.66f);",
    "presence-aware 3D body fade",
)
replace_once(
    "        const COLORREF line = mixColor (raw, RGB (248, 251, 255), 0.18f);",
    "        const float presence = clamp01 ((track.peakDb + 114.0f) / 78.0f);\n"
    "        const COLORREF lineBase = mixColor (raw, RGB (248, 251, 255), 0.16f);\n"
    "        const COLORREF line = mixColor (lineBase, RGB (16, 20, 26), (1.0f - presence) * 0.72f);",
    "presence-aware identity trace",
)

# UI language.
text = text.replace(
    "Stable Z ignores gain dynamics. Use Invert X / Invert Y if the DAW orientation reads backwards.",
    "Stable pose holds through silence. Invert drag X/Y changes mouse orbit direction only; room axes never flip."
)
text = text.replace(
    "X PAN   |   Y FREQUENCY   |   Z LATCHED DEPTH",
    "X PAN   |   Y FREQUENCY   |   Z LATCHED DEPTH"
)

out.write_text(text, encoding="utf-8")
print(out)
