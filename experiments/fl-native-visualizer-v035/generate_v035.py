from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
root = here.parent
v034 = root / "fl-native-visualizer-v034"

# Start from compile-green V0.34 render-truth diagnostics.
runpy.run_path(str(v034 / "generate_v034.py"), run_name="__main__")
src = v034 / "generated" / "fieldv034.cpp"
out = here / "generated" / "fieldv035.cpp"
out.parent.mkdir(parents=True, exist_ok=True)
text = src.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise RuntimeError(f"V0.35 could not find patch point: {label}")
    text = text.replace(old, new, 1)


# Identity. V0.35 is deliberately a presentation-layer fix: no DSP, route,
# spectral-profile, transient, pan, depth, or FX-analysis behavior changes.
text = text.replace("Field V0.34", "Field V0.35")
text = text.replace("FieldV034", "FieldV035")
text = text.replace("V034", "V035")
text = text.replace("v034", "v035")
text = text.replace("RENDER-TRUTH DIAGNOSTICS", "STABLE COMPOSITOR")

# -----------------------------------------------------------------------------
# 1) Independent ~60 Hz visual clock. The web prototype runs from
# requestAnimationFrame(); the native build previously depended on FL host Idle
# invalidations, which the V0.34 capture showed arriving at irregular 15-188 ms
# intervals. The timer only invalidates the editor; it never touches audio state.
replace_once(
    "            SetWindowLongPtrW (hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR> (self));\n",
    "            SetWindowLongPtrW (hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR> (self));\n"
    "            SetTimer (hwnd, 0xF135u, 16u, nullptr);\n",
    "start compositor timer",
)

replace_once(
    "            case WM_PAINT:\n                self->paint (hwnd);\n                return 0;",
    "            case WM_TIMER:\n"
    "                if (wParam == 0xF135u)\n"
    "                {\n"
    "                    InvalidateRect (hwnd, nullptr, FALSE);\n"
    "                    return 0;\n"
    "                }\n"
    "                break;\n"
    "            case WM_PAINT:\n"
    "                self->paint (hwnd);\n"
    "                return 0;",
    "60 Hz repaint timer",
)

# -----------------------------------------------------------------------------
# 2) Full-scene double buffering. Previously paint() cleared the real window HDC
# and then emitted room/grid/rings/labels one operation at a time. GDI/GDI+ can
# expose those intermediate states and produce exactly the disturbing flicker
# reported in V0.34. Compose the complete scene into a compatible memory bitmap,
# then present it with one BitBlt like a browser canvas/compositor frame.
replace_once(
    "        HDC dc = BeginPaint (hwnd, &ps);\n"
    "        updateDiagnosticPaintClock ();\n"
    "        RECT client {};\n"
    "        GetClientRect (hwnd, &client);",
    "        HDC windowDc = BeginPaint (hwnd, &ps);\n"
    "        updateDiagnosticPaintClock ();\n"
    "        RECT client {};\n"
    "        GetClientRect (hwnd, &client);\n"
    "        const int frameW = std::max (1, client.right - client.left);\n"
    "        const int frameH = std::max (1, client.bottom - client.top);\n"
    "        HDC backDc = CreateCompatibleDC (windowDc);\n"
    "        HBITMAP backBitmap = backDc ? CreateCompatibleBitmap (windowDc, frameW, frameH) : nullptr;\n"
    "        HGDIOBJ oldBackBitmap = nullptr;\n"
    "        HDC dc = windowDc;\n"
    "        if (backDc && backBitmap)\n"
    "        {\n"
    "            oldBackBitmap = SelectObject (backDc, backBitmap);\n"
    "            dc = backDc;\n"
    "        }",
    "double-buffer frame begin",
)

replace_once(
    "        maybeWriteDiagnostics ();\n"
    "        drawDiagnosticsOverlay (dc, client);\n"
    "        EndPaint (hwnd, &ps);",
    "        // V0.35 visual test: do not perform CSV open/write/close work inside\n"
    "        // the presentation path. V0.34 already captured the renderer-truth\n"
    "        // diagnostics needed to identify this compositor issue.\n"
    "        drawDiagnosticsOverlay (dc, client);\n"
    "        if (dc != windowDc)\n"
    "        {\n"
    "            BitBlt (windowDc, 0, 0, frameW, frameH, dc, 0, 0, SRCCOPY);\n"
    "            SelectObject (backDc, oldBackBitmap);\n"
    "            DeleteObject (backBitmap);\n"
    "            DeleteDC (backDc);\n"
    "        }\n"
    "        else\n"
    "        {\n"
    "            if (backBitmap) DeleteObject (backBitmap);\n"
    "            if (backDc) DeleteDC (backDc);\n"
    "        }\n"
    "        EndPaint (hwnd, &ps);",
    "atomic frame present",
)

text = text.replace(
    "V0.34 render-truth diagnostics: final GDI+ body state + real onset-to-draw timing",
    "V0.35 stable compositor: 60 Hz invalidation + full-scene backbuffer + atomic present"
)

out.write_text(text, encoding="utf-8")
print(out)
