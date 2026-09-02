#include "multibusview.h"
#include "multibuscontroller.h"
#include "multibusids.h"
#include "multibusstate.h"

#include "pluginterfaces/gui/iplugview.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>

namespace FieldMultiInputProbe {

using namespace Steinberg;

MultiBusView::MultiBusView (Controller* c) : controller (c)
{
    rect = ViewRect (0, 0, 850, 540);
    if (controller)
        controller->addRef ();
}

MultiBusView::~MultiBusView ()
{
    removed ();
    if (controller)
        controller->release ();
}

tresult PLUGIN_API MultiBusView::isPlatformTypeSupported (FIDString type)
{
#if SMTG_OS_WINDOWS
    return type && std::strcmp (type, kPlatformTypeHWND) == 0 ? kResultTrue : kResultFalse;
#else
    (void)type;
    return kResultFalse;
#endif
}

tresult PLUGIN_API MultiBusView::attached (void* parent, FIDString type)
{
#if SMTG_OS_WINDOWS
    if (!parent || isPlatformTypeSupported (type) != kResultTrue)
        return kResultFalse;

    static std::once_flag registerFlag;
    std::call_once (registerFlag, [] {
        WNDCLASSEXW wc {};
        wc.cbSize = sizeof (wc);
        wc.style = CS_HREDRAW | CS_VREDRAW;
        wc.lpfnWndProc = &MultiBusView::windowProc;
        wc.hInstance = GetModuleHandleW (nullptr);
        wc.hCursor = LoadCursorW (nullptr, IDC_ARROW);
        wc.lpszClassName = L"FieldMultiInputProbeView";
        RegisterClassExW (&wc);
    });

    systemWindow = parent;
    childWindow = CreateWindowExW (
        0, L"FieldMultiInputProbeView", L"", WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS,
        0, 0, rect.getWidth (), rect.getHeight (), static_cast<HWND> (parent), nullptr,
        GetModuleHandleW (nullptr), this);

    if (!childWindow)
    {
        systemWindow = nullptr;
        return kResultFalse;
    }

    SetTimer (childWindow, 1, 100, nullptr);
    return kResultTrue;
#else
    (void)parent; (void)type;
    return kResultFalse;
#endif
}

tresult PLUGIN_API MultiBusView::removed ()
{
#if SMTG_OS_WINDOWS
    if (childWindow)
    {
        KillTimer (childWindow, 1);
        DestroyWindow (childWindow);
        childWindow = nullptr;
    }
#endif
    systemWindow = nullptr;
    return kResultTrue;
}

tresult PLUGIN_API MultiBusView::onSize (ViewRect* newSize)
{
    if (!newSize)
        return kInvalidArgument;

    rect = *newSize;
#if SMTG_OS_WINDOWS
    if (childWindow)
        MoveWindow (childWindow, 0, 0, rect.getWidth (), rect.getHeight (), TRUE);
#endif
    return kResultTrue;
}

#if SMTG_OS_WINDOWS

static std::wstring utf8ToWide (const std::string& s)
{
    if (s.empty ())
        return {};
    const int needed = MultiByteToWideChar (CP_UTF8, 0, s.data (), static_cast<int> (s.size ()), nullptr, 0);
    if (needed <= 0)
        return std::wstring (s.begin (), s.end ());
    std::wstring out (static_cast<size_t> (needed), L'\0');
    MultiByteToWideChar (CP_UTF8, 0, s.data (), static_cast<int> (s.size ()), out.data (), needed);
    return out;
}

static std::wstring dbText (float db)
{
    if (db <= -119.0f)
        return L"-inf";
    wchar_t buf[32] {};
    swprintf_s (buf, L"%+.1f dB", db);
    return buf;
}

static int meterWidthForDb (float db, int maxWidth)
{
    const float t = std::clamp ((db + 60.0f) / 60.0f, 0.0f, 1.0f);
    return static_cast<int> (std::round (t * maxWidth));
}

LRESULT CALLBACK MultiBusView::windowProc (HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    MultiBusView* self = reinterpret_cast<MultiBusView*> (GetWindowLongPtrW (hwnd, GWLP_USERDATA));
    if (msg == WM_NCCREATE)
    {
        auto* cs = reinterpret_cast<CREATESTRUCTW*> (lParam);
        self = static_cast<MultiBusView*> (cs->lpCreateParams);
        SetWindowLongPtrW (hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR> (self));
    }

    return self ? self->handleMessage (hwnd, msg, wParam, lParam)
                : DefWindowProcW (hwnd, msg, wParam, lParam);
}

LRESULT MultiBusView::handleMessage (HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    switch (msg)
    {
        case WM_TIMER:
            InvalidateRect (hwnd, nullptr, FALSE);
            return 0;
        case WM_PAINT:
            paint (hwnd);
            return 0;
        case WM_ERASEBKGND:
            return 1;
        default:
            return DefWindowProcW (hwnd, msg, wParam, lParam);
    }
}

void MultiBusView::paint (HWND hwnd)
{
    PAINTSTRUCT ps {};
    HDC dc = BeginPaint (hwnd, &ps);

    RECT client {};
    GetClientRect (hwnd, &client);
    HBRUSH bg = CreateSolidBrush (RGB (17, 21, 27));
    FillRect (dc, &client, bg);
    DeleteObject (bg);

    SetBkMode (dc, TRANSPARENT);

    HFONT titleFont = CreateFontW (-24, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
                                   DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                   CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
    HFONT bodyFont = CreateFontW (-15, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                                  DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                  CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
    HFONT monoFont = CreateFontW (-15, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                                  DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                  CLEARTYPE_QUALITY, FIXED_PITCH, L"Consolas");

    auto oldFont = SelectObject (dc, titleFont);
    SetTextColor (dc, RGB (231, 237, 244));
    RECT r {18, 12, client.right - 18, 43};
    DrawTextW (dc, L"FIELD MULTI-INPUT PROBE", -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

    SelectObject (dc, bodyFont);
    SetTextColor (dc, RGB (137, 154, 173));
    r = {18, 43, client.right - 18, 79};
    DrawTextW (dc,
               L"One VST3 instance, eight stereo inputs. In FL Studio use SIDECHAIN routing for source tracks, then map those routes to the plugin inputs.",
               -1, &r, DT_LEFT | DT_WORDBREAK);

    const auto& state = sharedProbeState ();
    const auto block = state.processBlocks.load ();
    const auto channel = controller ? controller->getCurrentChannel () : std::string ("unknown");
    const auto channelWide = utf8ToWide (channel);

    SelectObject (dc, monoFont);
    SetTextColor (dc, RGB (95, 208, 194));
    wchar_t info[256] {};
    swprintf_s (info, L"Loaded on: %s    ProcessData: %d input buses / %d output buses    blocks: %llu",
                channelWide.c_str (), state.numInputsSeen.load (), state.numOutputsSeen.load (),
                static_cast<unsigned long long> (block));
    r = {18, 82, client.right - 18, 108};
    DrawTextW (dc, info, -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

    const int startY = 116;
    const int rowH = 44;
    const int labelX = 18;
    const int labelW = 150;
    const int meterX = 178;
    const int availableMeterWidth = static_cast<int> (client.right) - 178 - 250;
    const int meterW = std::max (180, availableMeterWidth);
    const int readoutX = meterX + meterW + 16;

    for (int i = 0; i < kInputBusCount; ++i)
    {
        const int y = startY + i * rowH;
        const float rms = state.rmsDb[i].load ();
        const float peak = state.peakDb[i].load ();
        const bool live = peak > -90.0f;
        const bool ever = state.signalSeen[i].load () > 0;

        SelectObject (dc, bodyFont);
        SetTextColor (dc, i == 0 ? RGB (95, 208, 194) : RGB (199, 211, 224));
        wchar_t label[64] {};
        swprintf_s (label, L"Input %d  %s", i + 1, i == 0 ? L"MAIN" : L"AUX");
        RECT lr {labelX, y + 5, labelX + labelW, y + 29};
        DrawTextW (dc, label, -1, &lr, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        RECT meterBg {meterX, y + 9, meterX + meterW, y + 27};
        HBRUSH meterBgBrush = CreateSolidBrush (RGB (31, 39, 49));
        FillRect (dc, &meterBg, meterBgBrush);
        DeleteObject (meterBgBrush);

        const int rmsW = meterWidthForDb (rms, meterW);
        if (rmsW > 0)
        {
            RECT rmsRect {meterX, y + 9, meterX + rmsW, y + 27};
            HBRUSH rmsBrush = CreateSolidBrush (live ? RGB (63, 216, 200) : RGB (73, 93, 110));
            FillRect (dc, &rmsRect, rmsBrush);
            DeleteObject (rmsBrush);
        }

        const int peakX = meterX + meterWidthForDb (peak, meterW);
        if (peakX > meterX)
        {
            HPEN peakPen = CreatePen (PS_SOLID, 2, peak > -1.0f ? RGB (255, 107, 86) : RGB (227, 235, 244));
            auto oldPen = SelectObject (dc, peakPen);
            MoveToEx (dc, peakX, y + 7, nullptr);
            LineTo (dc, peakX, y + 29);
            SelectObject (dc, oldPen);
            DeleteObject (peakPen);
        }

        SelectObject (dc, monoFont);
        SetTextColor (dc, RGB (224, 231, 239));
        const auto rmsText = dbText (rms);
        const auto peakText = dbText (peak);
        wchar_t values[128] {};
        swprintf_s (values, L"RMS %s   PK %s", rmsText.c_str (), peakText.c_str ());
        RECT vr {readoutX, y + 3, client.right - 78, y + 33};
        DrawTextW (dc, values, -1, &vr, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        SelectObject (dc, bodyFont);
        SetTextColor (dc, live ? RGB (126, 224, 138) : (ever ? RGB (190, 168, 92) : RGB (99, 112, 127)));
        RECT sr {client.right - 74, y + 3, client.right - 18, y + 33};
        DrawTextW (dc, live ? L"LIVE" : (ever ? L"SEEN" : L"---"), -1, &sr,
                   DT_RIGHT | DT_SINGLELINE | DT_VCENTER);

        HPEN rowPen = CreatePen (PS_SOLID, 1, RGB (39, 48, 60));
        auto oldPen = SelectObject (dc, rowPen);
        MoveToEx (dc, 18, y + rowH - 2, nullptr);
        LineTo (dc, client.right - 18, y + rowH - 2);
        SelectObject (dc, oldPen);
        DeleteObject (rowPen);
    }

    SelectObject (dc, bodyFont);
    const bool parallelRoute = state.parallelRouteDetected.load ();
    SetTextColor (dc, parallelRoute ? RGB (255, 122, 98) : RGB (137, 154, 173));
    r = {18, startY + kInputBusCount * rowH + 8, client.right - 18, client.bottom - 12};
    DrawTextW (dc,
               parallelRoute
                   ? L"PARALLEL ROUTING DETECTED. Main input already contains the same audio as the AUX inputs. Field Mix is de-duplicating it to prevent +6 dB. In FL use 'Sidechain to this track only' for Field source tracks."
                   : L"Routing OK. For the final Field hub, use 'Sidechain to this track only' so each source reaches Field once and its direct Master send is disabled. Stem Out 1..8 remain available for routing experiments.",
               -1, &r, DT_LEFT | DT_WORDBREAK);

    SelectObject (dc, oldFont);
    DeleteObject (titleFont);
    DeleteObject (bodyFont);
    DeleteObject (monoFont);
    EndPaint (hwnd, &ps);
}

#endif

} // namespace FieldMultiInputProbe
