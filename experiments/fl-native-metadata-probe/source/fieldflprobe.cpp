#include "fp_cplug.h"

#include <windows.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr int kMaxRoutes = 128;
HINSTANCE gDllInstance = nullptr;

char gLongName[] = "Field V0.02 Reconstruct Probe";
char gShortName[] = "FieldV002";

TFruityPlugInfo gPluginInfo = {
    CurrentSDKVersion,
    gLongName,
    gShortName,
    0,  // effect plugin
    0,  // params
    0,  // polyphony
    0,  // output controllers
    0,  // output voices
    {}
};

enum class MonitorMode : int
{
    Reference = 0,
    Reconstruct = 1,
    Null = 2
};

struct InputMetadata
{
    int routeIndex = 0;
    int mixerIndex = -1;
    int color = 0;
    std::string userName;
    std::string visibleName;
};

std::string boundedString (const char* text, size_t capacity)
{
    if (!text || capacity == 0)
        return {};
    size_t len = 0;
    while (len < capacity && text[len] != '\0')
        ++len;
    return std::string (text, len);
}

std::wstring ansiToWide (const std::string& text)
{
    if (text.empty ())
        return {};
    const int needed = MultiByteToWideChar (
        CP_ACP, 0, text.data (), static_cast<int> (text.size ()), nullptr, 0);
    if (needed <= 0)
        return std::wstring (text.begin (), text.end ());
    std::wstring result (static_cast<size_t> (needed), L'\0');
    MultiByteToWideChar (
        CP_ACP, 0, text.data (), static_cast<int> (text.size ()), result.data (), needed);
    return result;
}

float toDb (double linear)
{
    return static_cast<float> (20.0 * std::log10 (std::max (linear, 1.0e-6)));
}

void analyseStereo (PWAV32FS buffer, int length, float& rmsDb, float& peakDb)
{
    if (!buffer || length <= 0)
    {
        rmsDb = -120.0f;
        peakDb = -120.0f;
        return;
    }

    double sumSq = 0.0;
    double peak = 0.0;
    for (int i = 0; i < length; ++i)
    {
        const double l = buffer[i][0];
        const double r = buffer[i][1];
        sumSq += l * l + r * r;
        peak = std::max (peak, std::max (std::abs (l), std::abs (r)));
    }

    const double rms = std::sqrt (sumSq / static_cast<double> (length * 2));
    rmsDb = toDb (rms);
    peakDb = toDb (peak);
}

class FieldV002ReconstructProbe final : public TCPPFruityPlug
{
public:
    FieldV002ReconstructProbe (int tag, TFruityPlugHost* host)
        : TCPPFruityPlug (tag, host, gDllInstance)
    {
        Info = &gPluginInfo;
        for (auto& value : routePeakDb)
            value.store (-120.0f, std::memory_order_relaxed);
        PlugHost->Dispatcher (HostTag, FHD_WantIdle, 0, 2);
        refreshMetadata ();
    }

    void _stdcall DestroyObject () override
    {
        hideEditor ();
        TCPPFruityPlug::DestroyObject ();
    }

    intptr_t _stdcall Dispatcher (intptr_t id, intptr_t index, intptr_t value) override
    {
        switch (id)
        {
            case FPD_ShowEditor:
                if (value != 0)
                    showEditor (reinterpret_cast<HWND> (value));
                else
                    hideEditor ();
                return 1;

            case FPD_RoutingChanged:
                refreshMetadata ();
                if (editorWindow)
                    InvalidateRect (editorWindow, nullptr, TRUE);
                return 1;

            default:
                break;
        }
        return TCPPFruityPlug::Dispatcher (id, index, value);
    }

    void _stdcall Idle_Public () override
    {
        refreshMetadata ();
        if (editorWindow)
            InvalidateRect (editorWindow, nullptr, FALSE);
    }

    void _stdcall Eff_Render (PWAV32FS source, PWAV32FS dest, int length) override
    {
        if (!dest || length <= 0)
            return;

        PWAV32FS scratch = PlugHost->TempBuffers[0];
        if (scratch == source || scratch == dest)
            scratch = PlugHost->TempBuffers[1];

        if (!scratch || scratch == source || scratch == dest)
        {
            // Defensive fallback: preserve FL's normal summed audio rather than risk corruption.
            if (source && source != dest)
                std::memcpy (dest, source, static_cast<size_t> (length) * sizeof (TWAV32FS));
            return;
        }

        std::memset (scratch, 0, static_cast<size_t> (length) * sizeof (TWAV32FS));
        for (auto& value : routePeakDb)
            value.store (-120.0f, std::memory_order_relaxed);

        const int count = std::clamp (reportedRouteCount.load (std::memory_order_relaxed), 0, kMaxRoutes);
        int live = 0;

        for (int route = 1; route <= count; ++route)
        {
            TIOBuffer input {};
            PlugHost->GetInBuffer (HostTag, static_cast<intptr_t> (route), &input);

            if (!input.Buffer || (input.Flags & IO_Filled) == 0)
                continue;

            auto* routeBuffer = static_cast<PWAV32FS> (input.Buffer);
            double routePeak = 0.0;

            for (int i = 0; i < length; ++i)
            {
                const float l = routeBuffer[i][0];
                const float r = routeBuffer[i][1];
                scratch[i][0] += l;
                scratch[i][1] += r;
                routePeak = std::max (routePeak,
                                      std::max (std::abs (static_cast<double> (l)),
                                                std::abs (static_cast<double> (r))));
            }

            routePeakDb[static_cast<size_t> (route - 1)].store (
                toDb (routePeak), std::memory_order_relaxed);
            ++live;
        }

        liveRouteCount.store (live, std::memory_order_relaxed);

        float refRms = -120.0f, refPeak = -120.0f;
        float reconRms = -120.0f, reconPeak = -120.0f;
        float nRms = -120.0f, nPeak = -120.0f;

        analyseStereo (source, length, refRms, refPeak);
        analyseStereo (scratch, length, reconRms, reconPeak);

        // Compute null into a second FL-provided scratch buffer when possible.
        PWAV32FS nullBuffer = PlugHost->TempBuffers[2];
        if (nullBuffer && nullBuffer != source && nullBuffer != dest && nullBuffer != scratch)
        {
            for (int i = 0; i < length; ++i)
            {
                const float srcL = source ? source[i][0] : 0.0f;
                const float srcR = source ? source[i][1] : 0.0f;
                nullBuffer[i][0] = srcL - scratch[i][0];
                nullBuffer[i][1] = srcR - scratch[i][1];
            }
            analyseStereo (nullBuffer, length, nRms, nPeak);
        }

        referenceRmsDb.store (refRms, std::memory_order_relaxed);
        referencePeakDb.store (refPeak, std::memory_order_relaxed);
        reconstructRmsDb.store (reconRms, std::memory_order_relaxed);
        reconstructPeakDb.store (reconPeak, std::memory_order_relaxed);
        nullRmsDb.store (nRms, std::memory_order_relaxed);
        nullPeakDb.store (nPeak, std::memory_order_relaxed);

        const auto currentMode = static_cast<MonitorMode> (mode.load (std::memory_order_relaxed));

        if (currentMode == MonitorMode::Reference)
        {
            if (source && source != dest)
                std::memcpy (dest, source, static_cast<size_t> (length) * sizeof (TWAV32FS));
            else if (!source)
                std::memset (dest, 0, static_cast<size_t> (length) * sizeof (TWAV32FS));
        }
        else if (currentMode == MonitorMode::Reconstruct)
        {
            std::memcpy (dest, scratch, static_cast<size_t> (length) * sizeof (TWAV32FS));
        }
        else
        {
            if (nullBuffer)
                std::memcpy (dest, nullBuffer, static_cast<size_t> (length) * sizeof (TWAV32FS));
            else
                std::memset (dest, 0, static_cast<size_t> (length) * sizeof (TWAV32FS));
        }
    }

private:
    static LRESULT CALLBACK windowProc (HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam)
    {
        auto* self = reinterpret_cast<FieldV002ReconstructProbe*> (
            GetWindowLongPtrW (hwnd, GWLP_USERDATA));

        if (message == WM_NCCREATE)
        {
            auto* create = reinterpret_cast<CREATESTRUCTW*> (lParam);
            self = static_cast<FieldV002ReconstructProbe*> (create->lpCreateParams);
            SetWindowLongPtrW (hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR> (self));
        }

        if (!self)
            return DefWindowProcW (hwnd, message, wParam, lParam);

        switch (message)
        {
            case WM_LBUTTONUP:
                self->handleClick (GET_X_LPARAM (lParam), GET_Y_LPARAM (lParam));
                return 0;
            case WM_PAINT:
                self->paint (hwnd);
                return 0;
            case WM_ERASEBKGND:
                return 1;
            default:
                return DefWindowProcW (hwnd, message, wParam, lParam);
        }
    }

    void refreshMetadata ()
    {
        const intptr_t countResult = PlugHost->Dispatcher (HostTag, FHD_GetNumInOut, 0, 0);
        const int count = std::clamp (static_cast<int> (countResult), 0, kMaxRoutes);
        reportedRouteCount.store (count, std::memory_order_relaxed);

        std::vector<InputMetadata> next;
        next.reserve (static_cast<size_t> (count));

        for (int route = 1; route <= count; ++route)
        {
            TNameColor nc {};
            const intptr_t ok = PlugHost->Dispatcher (
                HostTag,
                FHD_GetInName,
                static_cast<intptr_t> (route),
                reinterpret_cast<intptr_t> (&nc));

            if (ok == 0)
                continue;

            InputMetadata item;
            item.routeIndex = route;
            item.mixerIndex = nc.Index;
            item.color = nc.Color;
            item.userName = boundedString (nc.Name, sizeof (nc.Name));
            item.visibleName = boundedString (nc.VisName, sizeof (nc.VisName));
            next.push_back (std::move (item));
        }

        inputs = std::move (next);
    }

    void handleClick (int x, int y)
    {
        if (y < 92 || y > 126)
            return;

        if (x >= 20 && x < 180)
            mode.store (static_cast<int> (MonitorMode::Reference), std::memory_order_relaxed);
        else if (x >= 190 && x < 350)
            mode.store (static_cast<int> (MonitorMode::Reconstruct), std::memory_order_relaxed);
        else if (x >= 360 && x < 520)
            mode.store (static_cast<int> (MonitorMode::Null), std::memory_order_relaxed);

        if (editorWindow)
            InvalidateRect (editorWindow, nullptr, FALSE);
    }

    void showEditor (HWND parent)
    {
        if (!parent)
            return;

        if (!editorWindow)
        {
            static bool registered = false;
            if (!registered)
            {
                WNDCLASSEXW wc {};
                wc.cbSize = sizeof (wc);
                wc.style = CS_HREDRAW | CS_VREDRAW;
                wc.lpfnWndProc = &FieldV002ReconstructProbe::windowProc;
                wc.hInstance = gDllInstance;
                wc.hCursor = LoadCursorW (nullptr, IDC_ARROW);
                wc.lpszClassName = L"FieldV002ReconstructProbeWindow";
                RegisterClassExW (&wc);
                registered = true;
            }

            editorWindow = CreateWindowExW (
                0,
                L"FieldV002ReconstructProbeWindow",
                L"",
                WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS,
                0, 0, 930, 610,
                parent,
                nullptr,
                gDllInstance,
                this);

            EditorHandle = editorWindow;
        }

        refreshMetadata ();
        ShowWindow (editorWindow, SW_SHOW);
        InvalidateRect (editorWindow, nullptr, TRUE);
    }

    void hideEditor ()
    {
        if (editorWindow)
        {
            DestroyWindow (editorWindow);
            editorWindow = nullptr;
            EditorHandle = nullptr;
        }
    }

    static void drawButton (HDC dc, const RECT& rect, const wchar_t* text, bool active)
    {
        HBRUSH brush = CreateSolidBrush (active ? RGB (42, 126, 116) : RGB (31, 39, 49));
        FillRect (dc, &rect, brush);
        DeleteObject (brush);
        FrameRect (dc, &rect, static_cast<HBRUSH> (GetStockObject (GRAY_BRUSH)));
        SetTextColor (dc, active ? RGB (239, 248, 246) : RGB (190, 203, 217));
        RECT textRect = rect;
        DrawTextW (dc, text, -1, &textRect, DT_CENTER | DT_SINGLELINE | DT_VCENTER);
    }

    void paint (HWND hwnd)
    {
        PAINTSTRUCT ps {};
        HDC dc = BeginPaint (hwnd, &ps);

        RECT client {};
        GetClientRect (hwnd, &client);
        HBRUSH background = CreateSolidBrush (RGB (16, 20, 26));
        FillRect (dc, &client, background);
        DeleteObject (background);
        SetBkMode (dc, TRANSPARENT);

        HFONT titleFont = CreateFontW (-25, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
                                       DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                       CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        HFONT bodyFont = CreateFontW (-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                                      DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                      CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        HFONT monoFont = CreateFontW (-15, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                                      DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                      CLEARTYPE_QUALITY, FIXED_PITCH, L"Consolas");

        auto oldFont = SelectObject (dc, titleFont);
        SetTextColor (dc, RGB (232, 238, 245));
        RECT r {20, 12, client.right - 20, 44};
        DrawTextW (dc, L"FIELD V0.02 - FL NATIVE ROUTE AUDIO RECONSTRUCTION", -1, &r,
                   DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        SelectObject (dc, bodyFont);
        SetTextColor (dc, RGB (143, 160, 178));
        r = {20, 45, client.right - 20, 82};
        DrawTextW (dc,
                   L"REFERENCE = FL normal sum. RECONSTRUCT = sum of individual routed input buffers. NULL = Reference minus Reconstruct.",
                   -1, &r, DT_LEFT | DT_WORDBREAK);

        const auto currentMode = static_cast<MonitorMode> (mode.load (std::memory_order_relaxed));
        RECT refButton {20, 92, 180, 126};
        RECT reconButton {190, 92, 350, 126};
        RECT nullButton {360, 92, 520, 126};
        drawButton (dc, refButton, L"REFERENCE", currentMode == MonitorMode::Reference);
        drawButton (dc, reconButton, L"RECONSTRUCT", currentMode == MonitorMode::Reconstruct);
        drawButton (dc, nullButton, L"NULL TEST", currentMode == MonitorMode::Null);

        SelectObject (dc, monoFont);
        wchar_t levels[320] {};
        swprintf_s (
            levels,
            L"Routes: %d   Live: %d    REF RMS %+.1f / PK %+.1f dB    RECON RMS %+.1f / PK %+.1f dB    NULL RMS %+.1f / PK %+.1f dB",
            reportedRouteCount.load (std::memory_order_relaxed),
            liveRouteCount.load (std::memory_order_relaxed),
            referenceRmsDb.load (std::memory_order_relaxed),
            referencePeakDb.load (std::memory_order_relaxed),
            reconstructRmsDb.load (std::memory_order_relaxed),
            reconstructPeakDb.load (std::memory_order_relaxed),
            nullRmsDb.load (std::memory_order_relaxed),
            nullPeakDb.load (std::memory_order_relaxed));

        const float nullPeak = nullPeakDb.load (std::memory_order_relaxed);
        SetTextColor (dc, nullPeak < -80.0f ? RGB (104, 221, 137) : RGB (244, 171, 91));
        r = {20, 134, client.right - 20, 162};
        DrawTextW (dc, levels, -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        SelectObject (dc, bodyFont);
        SetTextColor (dc, RGB (111, 126, 143));
        r = {20, 170, client.right - 20, 194};
        DrawTextW (dc, L"ROUTE   COLOR   MIXER   NAME                                      LIVE PEAK", -1, &r,
                   DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        const int startY = 196;
        const int rowHeight = 43;
        for (size_t i = 0; i < inputs.size (); ++i)
        {
            const auto& item = inputs[i];
            const int y = startY + static_cast<int> (i) * rowHeight;
            if (y + rowHeight > client.bottom - 42)
                break;

            HPEN linePen = CreatePen (PS_SOLID, 1, RGB (39, 48, 59));
            auto oldPen = SelectObject (dc, linePen);
            MoveToEx (dc, 20, y + rowHeight - 2, nullptr);
            LineTo (dc, client.right - 20, y + rowHeight - 2);
            SelectObject (dc, oldPen);
            DeleteObject (linePen);

            wchar_t routeText[32] {};
            swprintf_s (routeText, L"%d", item.routeIndex);
            RECT routeRect {20, y, 70, y + 34};
            SetTextColor (dc, RGB (222, 229, 237));
            DrawTextW (dc, routeText, -1, &routeRect, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

            RECT swatch {76, y + 7, 108, y + 29};
            HBRUSH colorBrush = CreateSolidBrush (static_cast<COLORREF> (item.color & 0x00FFFFFF));
            FillRect (dc, &swatch, colorBrush);
            DeleteObject (colorBrush);
            FrameRect (dc, &swatch, static_cast<HBRUSH> (GetStockObject (GRAY_BRUSH)));

            wchar_t indexText[32] {};
            swprintf_s (indexText, L"%d", item.mixerIndex);
            RECT indexRect {124, y, 194, y + 34};
            DrawTextW (dc, indexText, -1, &indexRect, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

            std::string display = !item.visibleName.empty () ? item.visibleName : item.userName;
            if (display.empty ())
                display = "(unnamed)";
            const auto wide = ansiToWide (display);
            RECT nameRect {204, y, client.right - 150, y + 34};
            SetTextColor (dc, RGB (207, 218, 229));
            DrawTextW (dc, wide.c_str (), -1, &nameRect,
                       DT_LEFT | DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);

            float peak = -120.0f;
            if (item.routeIndex >= 1 && item.routeIndex <= kMaxRoutes)
                peak = routePeakDb[static_cast<size_t> (item.routeIndex - 1)].load (std::memory_order_relaxed);
            wchar_t peakText[48] {};
            swprintf_s (peakText, L"%+.1f dB", peak);
            RECT peakRect {client.right - 140, y, client.right - 20, y + 34};
            SetTextColor (dc, peak > -90.0f ? RGB (104, 221, 137) : RGB (105, 119, 135));
            DrawTextW (dc, peakText, -1, &peakRect, DT_RIGHT | DT_SINGLELINE | DT_VCENTER);
        }

        SelectObject (dc, bodyFont);
        SetTextColor (dc, RGB (143, 160, 178));
        r = {20, client.bottom - 36, client.right - 20, client.bottom - 10};
        DrawTextW (dc,
                   L"For the cleanest test, load this on Master and do not place audio generators directly on the Master track. Start with RECONSTRUCT, then click NULL TEST.",
                   -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);

        SelectObject (dc, oldFont);
        DeleteObject (titleFont);
        DeleteObject (bodyFont);
        DeleteObject (monoFont);
        EndPaint (hwnd, &ps);
    }

    HWND editorWindow = nullptr;
    std::vector<InputMetadata> inputs;

    std::atomic<int> mode {static_cast<int> (MonitorMode::Reconstruct)};
    std::atomic<int> reportedRouteCount {0};
    std::atomic<int> liveRouteCount {0};
    std::array<std::atomic<float>, kMaxRoutes> routePeakDb;

    std::atomic<float> referenceRmsDb {-120.0f};
    std::atomic<float> referencePeakDb {-120.0f};
    std::atomic<float> reconstructRmsDb {-120.0f};
    std::atomic<float> reconstructPeakDb {-120.0f};
    std::atomic<float> nullRmsDb {-120.0f};
    std::atomic<float> nullPeakDb {-120.0f};
};

} // namespace

BOOL WINAPI DllMain (HINSTANCE instance, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
        gDllInstance = instance;
    return TRUE;
}

extern "C" __declspec(dllexport) TFruityPlug* _stdcall
CreatePlugInstance (TFruityPlugHost* host, int tag)
{
    return new FieldV002ReconstructProbe (tag, host);
}
