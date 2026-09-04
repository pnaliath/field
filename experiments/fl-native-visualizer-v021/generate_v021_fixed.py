from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
runpy.run_path(str(here / "generate_v021.py"), run_name="__main__")
out = here / "generated" / "fieldv021.cpp"
text = out.read_text(encoding="utf-8")

old_header = "tick_ms,route,name,block_ms,render_ms,render_pct,paint_ms,peak_db,fast_rms_db,presence,learned_loud_db,z,profile_ready,dominant_hz,low_hz,high_hz,onset_count,onset_to_presence_ms,onset_to_profile_ms,onset_to_draw_ms\\n"
new_header = "tick_ms,route,name,block_ms,render_ms,render_pct,paint_ms,peak_db,fast_rms_db,presence,learned_loud_db,z,profile_ready,dominant_hz,low_hz,high_hz,onset_count,onset_to_presence_ms,onset_to_profile_ms,onset_to_draw_ms,voice_count,voice_pan_0,voice_pan_1,voice_pan_2\\n"
if old_header not in text:
    raise RuntimeError("V0.21 diagnostics header marker not found")
text = text.replace(old_header, new_header, 1)

old_fmt = "%llu,%d,%s,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.4f,%.2f,%.4f,%d,%.1f,%.1f,%.1f,%u,%.1f,%.1f,%.1f\\n"
new_fmt = "%llu,%d,%s,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%.4f,%.2f,%.4f,%d,%.1f,%.1f,%.1f,%u,%.1f,%.1f,%.1f,%d,%.4f,%.4f,%.4f\\n"
if old_fmt not in text:
    raise RuntimeError("V0.21 diagnostics row format marker not found")
text = text.replace(old_fmt, new_fmt, 1)

old_tail = "                diagProfileDelayMs[idx].load (std::memory_order_relaxed),\n                diagDrawDelayMs[idx].load (std::memory_order_relaxed));"
new_tail = "                diagProfileDelayMs[idx].load (std::memory_order_relaxed),\n                diagDrawDelayMs[idx].load (std::memory_order_relaxed),\n                spatialVoiceCount[idx].load (std::memory_order_relaxed),\n                spatialVoicePan[idx][0].load (std::memory_order_relaxed),\n                spatialVoicePan[idx][1].load (std::memory_order_relaxed),\n                spatialVoicePan[idx][2].load (std::memory_order_relaxed));"
if old_tail not in text:
    raise RuntimeError("V0.21 diagnostics row tail marker not found")
text = text.replace(old_tail, new_tail, 1)

out.write_text(text, encoding="utf-8")
print(out)
