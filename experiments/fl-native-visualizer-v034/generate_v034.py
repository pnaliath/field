from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v033 = root / "fl-native-visualizer-v033"

# Start from the compile-green V0.33 renderer-parity build. V0.34 is intentionally
# diagnostics-only: it must not alter analysis, source classification, spatial
# behavior, audio reconstruction, or the GDI+ visual grammar.
runpy.run_path(str(v033 / "generate_v033_fixed.py"), run_name="__main__")
src = v033 / "generated" / "fieldv033.cpp"
out = here / "generated" / "fieldv034.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.34 could not find patch point: {label}")
    text = text.replace(old, new, 1)


# Fresh identity / log filename.
text = text.replace("Field V0.33", "Field V0.34")
text = text.replace("FieldV033", "FieldV034")
text = text.replace("V033", "V034")
text = text.replace("v033", "v034")
text = text.replace("WEB RENDER PARITY", "RENDER-TRUTH DIAGNOSTICS")

# -----------------------------------------------------------------------------
# Final-render telemetry. The inherited V0.18 diagnostic Z hook was attached to
# an older depth path and V0.33 replaced drawSpectralBody(), which also removed
# stampDiagnosticDraw(). The result was a constant z=.5 and onset_to_draw_ms=-1
# even when the new GDI+ renderer was visibly drawing. These cells are written
# only at the point where the final renderer has passed every eligibility gate.
replace_once(
    "    std::array<std::atomic<float>, kMaxRoutes> diagVisualZ;\n",
    "    std::array<std::atomic<float>, kMaxRoutes> diagVisualZ;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> diagRenderX;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> diagRenderWidth;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> diagRenderPresence;\n"
    "    std::array<std::atomic<int>, kMaxRoutes> diagRenderVoiceIndex;\n"
    "    std::array<std::atomic<int>, kMaxRoutes> diagRenderVoiceCount;\n"
    "    std::array<std::atomic<bool>, kMaxRoutes> diagRenderEventSnapshot;\n"
    "    std::array<std::atomic<int>, kMaxRoutes> diagRenderLobeCount;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> diagRenderDominantHz;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> diagRenderLowHz;\n"
    "    std::array<std::atomic<float>, kMaxRoutes> diagRenderHighHz;\n"
    "    std::array<std::atomic<unsigned long long>, kMaxRoutes> diagLastRenderedMs;\n",
    "final render diagnostic members",
)

replace_once(
    "        for (auto& v : diagVisualZ) v.store (0.5f, std::memory_order_relaxed);",
    "        for (auto& v : diagVisualZ) v.store (0.5f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagRenderX) v.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagRenderWidth) v.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagRenderPresence) v.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagRenderVoiceIndex) v.store (0, std::memory_order_relaxed);\n"
    "        for (auto& v : diagRenderVoiceCount) v.store (0, std::memory_order_relaxed);\n"
    "        for (auto& v : diagRenderEventSnapshot) v.store (false, std::memory_order_relaxed);\n"
    "        for (auto& v : diagRenderLobeCount) v.store (0, std::memory_order_relaxed);\n"
    "        for (auto& v : diagRenderDominantHz) v.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagRenderLowHz) v.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagRenderHighHz) v.store (0.0f, std::memory_order_relaxed);\n"
    "        for (auto& v : diagLastRenderedMs) v.store (0ull, std::memory_order_relaxed);",
    "final render diagnostic initialization",
)

# The V0.33 renderer has already checked: valid route, display profile ready,
# presence > threshold, and at least one drawable lobe. Stamp diagnostics only
# after those checks, immediately before geometry is emitted to GDI+.
render_truth = r'''        // V0.34 renderer truth. Everything below describes the body that is
        // ACTUALLY eligible to be painted, not an upstream learner/interpolator.
        float renderLowHz = 0.0f;
        float renderHighHz = 0.0f;
        float renderDominantHz = 0.0f;
        float renderDominantEnergy = -1.0f;
        for (const auto& lobe : lobes)
        {
            for (int i = lobe.first; i <= lobe.second; ++i)
            {
                const float hz = bandHz[static_cast<size_t> (i)].load (std::memory_order_relaxed);
                const float e = shape[static_cast<size_t> (i)];
                if (renderLowHz <= 0.0f)
                    renderLowHz = hz;
                renderHighHz = hz;
                if (e > renderDominantEnergy)
                {
                    renderDominantEnergy = e;
                    renderDominantHz = hz;
                }
            }
        }

        diagVisualZ[routeIndex].store (track.visualZ, std::memory_order_relaxed);
        diagRenderX[routeIndex].store (track.balance, std::memory_order_relaxed);
        diagRenderWidth[routeIndex].store (track.width, std::memory_order_relaxed);
        diagRenderPresence[routeIndex].store (presence, std::memory_order_relaxed);
        diagRenderVoiceIndex[routeIndex].store (track.spatialVoiceIndex, std::memory_order_relaxed);
        diagRenderVoiceCount[routeIndex].store (track.spatialVoiceCount, std::memory_order_relaxed);
        diagRenderEventSnapshot[routeIndex].store (track.eventSnapshot, std::memory_order_relaxed);
        diagRenderLobeCount[routeIndex].store (static_cast<int> (lobes.size ()), std::memory_order_relaxed);
        diagRenderDominantHz[routeIndex].store (renderDominantHz, std::memory_order_relaxed);
        diagRenderLowHz[routeIndex].store (renderLowHz, std::memory_order_relaxed);
        diagRenderHighHz[routeIndex].store (renderHighHz, std::memory_order_relaxed);
        diagLastRenderedMs[routeIndex].store (GetTickCount64 (), std::memory_order_release);
        stampDiagnosticDraw (routeIndex);

'''
replace_once(
    "        if (lobes.empty ())\n            return;\n\n        auto baseHalfPan",
    "        if (lobes.empty ())\n            return;\n\n" + render_truth + "        auto baseHalfPan",
    "stamp final GDI+ render truth",
)

# -----------------------------------------------------------------------------
# Extend the existing CSV rather than replacing it, so V0.18-V0.33 captures stay
# directly comparable. The old 'z' column is also fixed because diagVisualZ is now
# stamped from the actual DrawTrack reaching the GDI+ renderer.
old_header = "tick_ms,route,name,block_ms,render_ms,render_pct,paint_ms,peak_db,fast_rms_db,presence,learned_loud_db,z,profile_ready,dominant_hz,low_hz,high_hz,onset_count,onset_to_presence_ms,onset_to_profile_ms,onset_to_draw_ms,voice_count,voice_pan_0,voice_pan_1,voice_pan_2,live_pan,live_width,depth_level_db,pan_shift,x_sens,z_sens,disappear_ms,eq_hz,eq_db\\n"
new_header = "tick_ms,route,name,block_ms,render_ms,render_pct,paint_ms,peak_db,fast_rms_db,presence,learned_loud_db,z,profile_ready,dominant_hz,low_hz,high_hz,onset_count,onset_to_presence_ms,onset_to_profile_ms,onset_to_draw_ms,voice_count,voice_pan_0,voice_pan_1,voice_pan_2,live_pan,live_width,depth_level_db,pan_shift,x_sens,z_sens,disappear_ms,eq_hz,eq_db,display_profile_ready,render_x,render_z,render_width,render_presence,render_voice_index,render_voice_count,render_event_snapshot,render_lobes,render_dominant_hz,render_low_hz,render_high_hz,last_render_age_ms\\n"
replace_once(old_header, new_header, "render-truth diagnostics header")

old_fmt = "%llu,%d,%s,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.4f,%.2f,%.4f,%d,%.1f,%.1f,%.1f,%u,%.1f,%.1f,%.1f,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%.4f,%.2f,%.2f,%.0f,%.1f,%.2f\\n"
new_fmt = "%llu,%d,%s,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.4f,%.2f,%.4f,%d,%.1f,%.1f,%.1f,%u,%.1f,%.1f,%.1f,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%.4f,%.2f,%.2f,%.0f,%.1f,%.2f,%d,%.4f,%.4f,%.4f,%.4f,%d,%d,%d,%d,%.1f,%.1f,%.1f,%.1f\\n"
replace_once(old_fmt, new_fmt, "render-truth diagnostics row format")

old_tail = "                disappearTimeMs,\n                routeEqDiagHz[idx].load (std::memory_order_relaxed),\n                routeEqDiagDb[idx].load (std::memory_order_relaxed));"
new_tail = "                disappearTimeMs,\n                routeEqDiagHz[idx].load (std::memory_order_relaxed),\n                routeEqDiagDb[idx].load (std::memory_order_relaxed),\n                routeDisplayProfileReady[idx].load (std::memory_order_relaxed) ? 1 : 0,\n                diagRenderX[idx].load (std::memory_order_relaxed),\n                diagVisualZ[idx].load (std::memory_order_relaxed),\n                diagRenderWidth[idx].load (std::memory_order_relaxed),\n                diagRenderPresence[idx].load (std::memory_order_relaxed),\n                diagRenderVoiceIndex[idx].load (std::memory_order_relaxed),\n                diagRenderVoiceCount[idx].load (std::memory_order_relaxed),\n                diagRenderEventSnapshot[idx].load (std::memory_order_relaxed) ? 1 : 0,\n                diagRenderLobeCount[idx].load (std::memory_order_relaxed),\n                diagRenderDominantHz[idx].load (std::memory_order_relaxed),\n                diagRenderLowHz[idx].load (std::memory_order_relaxed),\n                diagRenderHighHz[idx].load (std::memory_order_relaxed),\n                diagLastRenderedMs[idx].load (std::memory_order_acquire) == 0ull ? -1.0f :\n                    static_cast<float> (now - diagLastRenderedMs[idx].load (std::memory_order_relaxed)));"
replace_once(old_tail, new_tail, "render-truth diagnostics row tail")

text = text.replace(
    "V0.33 renderer parity: GDI+ real alpha/AA + browser stacked rings/contours/silhouette",
    "V0.34 render-truth diagnostics: final GDI+ body state + real onset-to-draw timing"
)

out.write_text(text, encoding="utf-8")
print(out)
