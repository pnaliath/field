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

char gLongName[] = "Field V0.03 Reconstruct Probe";
char gShortName[] = "FieldV003";

TFruityPlugInfo gPluginInfo = {
    CurrentSDKVersion,
    gLongName,
    gShortName,
    0, 0, 0, 0, 0, {}
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
    const int needed = MultiByteToWideChar (CP_ACP, 0, text.data (), static_cast<int> (text.size ()), nullptr, 0);
    if (needed <= 0)
        return std::wstring (text.begin (), text.end ());
    std::wstring out (static_cast<size_t> (needed), L'\0');
    MultiByteToWideChar (CP_ACP, 0, text.data (), static_cast<int> (text.size ()), out.data (), needed);
    return out;
}

float toDb (double linear)
{
    return static_cast<float> (20.0 * std::log10 (std::max (linear, 1.0e-6)));
}

void analyseStereo (PWAV32FS buffer, int length, float& rmsDb, float& peakDb)
{
    if (!buffer || length <= 0)
    {
        rmsDb = peakDb = -120.0f;
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

class FieldV003ReconstructProbe final : public TCPPFruityPlug
{
public:
    FieldV003ReconstructProbe (int tag, TFruityPlugHost* host)
        : TCPPFruityPlug (tag, host, gDllInstance)
    {
        Info = &gPluginInfo;
        for (auto& p : routePeakDb)
            p.store (-120.0f, std::memory_order_relaxed);

        // Keep construction deliberately minimal. Metadata and route enumeration
        // happen later on FL's UI/idle path, not while the plugin is being created.
        PlugHost->Dispatcher (HostTag, FHD_WantIdle, 0, 2);
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

        float refRms = -120.0f, refPeak = -120.0f;
        analyseStereo (source, length, refRms, refPeak);
        referenceRmsDb.store (refRms, std::memory_order_relaxed);
        referencePeakDb.store (refPeak, std::memory_order_relaxed);

        const auto currentMode = static_cast<MonitorMode> (mode.load (std::memory_order_relaxed));

        // Safe startup path: no GetInBuffer calls at all until the user explicitly
        // selects RECONSTRUCT or NULL in the plugin UI.
        if (currentMode == MonitorMode::Reference)
        {
            reconstructRmsDb.store (-120.0f, std::memory_order_relaxed);
            reconstructPeakDb.store (-120.0f, std::memory_order_relaxed);
            nullRmsDb.store (-120.0f, std::memory_order_relaxed);
            nullPeakDb.store (-120.0f, std::memory_order_relaxed);
            liveRouteCount.store (0, std::memory_order_relaxed);
            if (source && source != dest)
                std::memcpy (dest, source, static_cast<size_t> (length) * sizeof (TWAV32FS));
            else if (!source)
                std::memset (dest, 0, static_cast<size_t> (length) * sizeof (TWAV32FS));
            return;
        }

        PWAV32FS recon = PlugHost->TempBuffers[0];
        if (!recon || recon == source || recon == dest)
            recon = PlugHost->TempBuffers[1];

        if (!recon || recon == source || recon == dest)
        {
            // Never break audio if FL does not provide a safe scratch buffer.
            if (source && source != dest)
                std::memcpy (dest, source, static_cast<size_t> (length) * sizeof (TWAV32FS));
            return;
        }

        std::memset (recon, 0, static_cast<size_t> (length) * sizeof (TWAV32FS));
        for (auto& p : routePeakDb)
            p.store (-120.0f, std::memory_order_relaxed);

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
                recon[i][0] += l;
                recon[i][1] += r;
                routePeak = std::max (routePeak,
                    std::max (std::abs (static_cast<double> (l)), std::abs (static_cast<double> (r))));
            }

            routePeakDb[static_cast<size_t> (route - 1)].store (toDb (routePeak), std::memory_order_relaxed);
            ++live;
        }

        liveRouteCount.store (live, std::memory_order_relaxed);

        float reconRms = -120.0f, reconPeak = -120.0f;
        analyseStereo (recon, length, reconRms, reconPeak);
        reconstructRmsDb.store (reconRms, std::memory_order_relaxed);
        reconstructPeakDb.store (reconPeak, std::memory_order_relaxed);

        if (currentMode == MonitorMode::Reconstruct)
        {
            nullRmsDb.store (-120.0f, std::memory_order_relaxed);
            nullPeakDb.store (-120.0f, std::memory_order_relaxed);
            std::memcpy (dest, recon, static_cast<size_t> (length) * sizeof (TWAV32FS));
            return;
        }

        // NULL mode: output Reference - Reconstruct.
        double nullSumSq = 0.0;
        double nullPeak = 0.0;
        for (int i = 0; i < length; ++i)
        {
            const float refL = source ? source[i][0] : 0.0f;
            const float refR = source ? source[i][1] : 0.0f;
            const float l = refL - recon[i][0];
            const float r = refR - recon[i][1];
            dest[i][0] = l;
            dest[i][1] = r;
            nullSumSq += static_cast<double> (l) * l + static_cast<double> (r) * r;
            nullPeak = std::max (nullPeak,
                std::max (std::abs (static_cast<double> (l)), std::abs (static_cast<double> (r))));
        }
        const double nullRms = std::sqrt (nullSumSq / static_cast<double> (length * 2));
        nullRmsDb.store (toDb (nullRms), std::memory_order_relaxed);
        nullPeakDb.store (toDb (nullPeak), std::memory_order_relaxed);
    }

private:
    static LRESULT CALLBACK windowProc (HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam)
    {
        auto* self = reinterpret_cast<FieldV003ReconstructProbe*> (GetWindowLongPtrW (hwnd, GWLP_USERDATA));
        if (message == WM_NCCREATE)
        {
            auto* create = reinterpret_cast<CREATESTRUCTW*> (lParam);
            self = static_cast<FieldV003ReconstructProbe*> (create->lpCreateParams);
            SetWindowLongPtrW (hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR> (self));
        }
        if (!self)
            return DefWindowProcW (hwnd, message, wParam, lParam);

        switch (message)
        {
            case WM_LBUTTONUP:
                self->handleClick (static_cast<int> (static_cast<short> (LOWORD (lParam))),
                                   static_cast<int> (static_cast<short> (HIWORD (lParam))));
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
                HostTag, FHD_GetInName, static_cast<intptr_t> (route), reinterpret_cast<intptr_t> (&nc));
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
        if (y < 92 || y > 128)
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
                wc.lpfnWndProc = &FieldV003ReconstructProbe::windowProc;
                wc.hInstance = gDllInstance;
                wc.hCursor = LoadCursorW (nullptr, IDC_ARROW);
                wc.lpszClassName = L"FieldV003ReconstructProbeWindow";
                RegisterClassExW (&wc);
                registered = true;
            }

            editorWindow = CreateWindowExW (
                0, L"FieldV003ReconstructProbeWindow", L"", WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS,
                0, 0, 950, 620, parent, nullptr, gDllInstance, this);
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
        RECT tr = rect;
        DrawTextW (dc, text, -1, &tr, DT_CENTER | DT_SINGLELINE | DT_VCENTER);
    }

    void paint (HWND hwnd)
    {
        PAINTSTRUCT ps {};
        HDC dc = BeginPaint (hwnd, &ps);
        RECT client {};
        GetClientRect (hwnd, &client);

        HBRUSH bg = CreateSolidBrush (RGB (16, 20, 26));
        FillRect (dc, &client, bg);
        DeleteObject (bg);
        SetBkMode (dc, TRANSPARENT);

        HFONT titleFont = CreateFontW (-25, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        HFONT bodyFont = CreateFontW (-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        HFONT monoFont = CreateFontW (-15, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, FIXED_PITCH, L"Consolas");

        auto oldFont = SelectObject (dc, titleFont);
        SetTextColor (dc, RGB (232, 238, 245));
        RECT r {20, 12, client.right - 20, 44};
        DrawTextW (dc, L"FIELD V0.03 - FL NATIVE ROUTE AUDIO RECONSTRUCTION", -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        SelectObject (dc, bodyFont);
        SetTextColor (dc, RGB (143, 160, 178));
        r = {20, 46, client.right - 20, 82};
        DrawTextW (dc,
            L"Starts in safe REFERENCE mode. RECONSTRUCT reads each native routed input buffer once. NULL outputs Reference - Reconstruct.",
            -1, &r, DT_LEFT | DT_WORDBREAK);

        const auto m = static_cast<MonitorMode> (mode.load (std::memory_order_relaxed));
        RECT b1 {20, 92, 180, 128};
        RECT b2 {190, 92, 350, 128};
        RECT b3 {360, 92, 520, 128};
        drawButton (dc, b1, L"REFERENCE", m == MonitorMode::Reference);
        drawButton (dc, b2, L"RECONSTRUCT", m == MonitorMode::Reconstruct);
        drawButton (dc, b3, L"NULL TEST", m == MonitorMode::Null);

        SelectObject (dc, monoFont);
        wchar_t meters[512] {};
        swprintf_s (meters,
            L"REF  RMS %+.1f dB  PK %+.1f dB    RECON  RMS %+.1f dB  PK %+.1f dB    NULL  RMS %+.1f dB  PK %+.1f dB",
            referenceRmsDb.load (), referencePeakDb.load (),
            reconstructRmsDb.load (), reconstructPeakDb.load (),
            nullRmsDb.load (), nullPeakDb.load ());
        SetTextColor (dc, RGB (91, 210, 195));
        r = {20, 136, client.right - 20, 162};
        DrawTextW (dc, meters, -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        wchar_t counts[160] {};
        swprintf_s (counts, L"Host routes: %d    Live routed buffers: %d",
            reportedRouteCount.load (), liveRouteCount.load ());
        r = {20, 162, client.right - 20, 188};
        DrawTextW (dc, counts, -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        const int startY = 218;
        const int rowH = 36;
        SelectObject (dc, bodyFont);
        SetTextColor (dc, RGB (111, 126, 143));
        r = {20, 190, client.right - 20, 216};
        DrawTextW (dc, L"ROUTE   COLOR   MIXER   TRACK NAME                                      LIVE PEAK", -1, &r,
            DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        for (size_t i = 0; i < inputs.size (); ++i)
        {
            const auto& item = inputs[i];
            const int y = startY + static_cast<int> (i) * rowH;
            if (y + rowH > client.bottom - 12)
                break;

            HPEN pen = CreatePen (PS_SOLID, 1, RGB (39, 48, 59));
            auto oldPen = SelectObject (dc, pen);
            MoveToEx (dc, 20, y + rowH - 1, nullptr);
            LineTo (dc, client.right - 20, y + rowH - 1);
            SelectObject (dc, oldPen);
            DeleteObject (pen);

            wchar_t routeText[24] {};
            swprintf_s (routeText, L"%d", item.routeIndex);
            RECT rr {20, y, 70, y + 30};
            SetTextColor (dc, RGB (222, 229, 237));
            DrawTextW (dc, routeText, -1, &rr, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

            RECT swatch {76, y + 6, 108, y + 28};
            HBRUSH cb = CreateSolidBrush (static_cast<COLORREF> (item.color & 0x00FFFFFF));
            FillRect (dc, &swatch, cb);
            DeleteObject (cb);

            wchar_t indexText[24] {};
            swprintf_s (indexText, L"%d", item.mixerIndex);
            RECT ir {122, y, 205, y + 30};
            DrawTextW (dc, indexText, -1, &ir, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

            std::string display = !item.visibleName.empty () ? item.visibleName : item.userName;
            if (display.empty ()) display = "(unnamed)";
            auto wide = ansiToWide (display);
            RECT nr {210, y, client.right - 150, y + 30};
            DrawTextW (dc, wide.c_str (), -1, &nr, DT_LEFT | DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);

            const float peak = item.routeIndex >= 1 && item.routeIndex <= kMaxRoutes
                ? routePeakDb[static_cast<size_t> (item.routeIndex - 1)].load () : -120.0f;
            wchar_t peakText[48] {};
            if (peak <= -119.0f)
                swprintf_s (peakText, L"---");
            else
                swprintf_s (peakText, L"%+.1f dB", peak);
            RECT pr {client.right - 135, y, client.right - 20, y + 30};
            SetTextColor (dc, peak > -90.0f ? RGB (126, 224, 138) : RGB (124, 139, 156));
            DrawTextW (dc, peakText, -1, &pr, DT_RIGHT | DT_SINGLELINE | DT_VCENTER);
        }

        SelectObject (dc, oldFont);
        DeleteObject (titleFont);
        DeleteObject (bodyFont);
        DeleteObject (monoFont);
        EndPaint (hwnd, &ps);
    }

    HWND editorWindow = nullptr;
    std::vector<InputMetadata> inputs;
    std::array<std::atomic<float>, kMaxRoutes> routePeakDb;
    std::atomic<int> reportedRouteCount {0};
    std::atomic<int> liveRouteCount {0};
    std::atomic<int> mode {static_cast<int> (MonitorMode::Reference)};
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
    return new FieldV003ReconstructProbe (tag, host);
}
