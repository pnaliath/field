#include "routeprobeview.h"
#include "routeprobecontroller.h"

#include "pluginterfaces/gui/iplugview.h"

#include <array>
#include <cstring>
#include <mutex>
#include <string>

namespace FieldRouteProbe {

using namespace Steinberg;

RouteProbeView::RouteProbeView (Controller* c) : controller (c)
{
    rect = ViewRect (0, 0, 780, 455);
    if (controller)
        controller->addRef ();
}

RouteProbeView::~RouteProbeView ()
{
    removed ();
    if (controller)
        controller->release ();
}

tresult PLUGIN_API RouteProbeView::isPlatformTypeSupported (FIDString type)
{
#if SMTG_OS_WINDOWS
    return type && std::strcmp (type, kPlatformTypeHWND) == 0 ? kResultTrue : kResultFalse;
#else
    (void)type;
    return kResultFalse;
#endif
}

tresult PLUGIN_API RouteProbeView::attached (void* parent, FIDString type)
{
#if SMTG_OS_WINDOWS
    if (!parent || isPlatformTypeSupported (type) != kResultTrue)
        return kResultFalse;

    static std::once_flag registerFlag;
    std::call_once (registerFlag, [] {
        WNDCLASSEXW wc {};
        wc.cbSize = sizeof (wc);
        wc.style = CS_HREDRAW | CS_VREDRAW;
        wc.lpfnWndProc = &RouteProbeView::windowProc;
        wc.hInstance = GetModuleHandleW (nullptr);
        wc.hCursor = LoadCursorW (nullptr, IDC_ARROW);
        wc.lpszClassName = L"FieldRouteProbeDiagnosticView";
        RegisterClassExW (&wc);
    });

    systemWindow = parent;
    childWindow = CreateWindowExW (
        0, L"FieldRouteProbeDiagnosticView", L"", WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS,
        0, 0, rect.getWidth (), rect.getHeight (), static_cast<HWND> (parent), nullptr,
        GetModuleHandleW (nullptr), this);

    if (!childWindow)
    {
        systemWindow = nullptr;
        return kResultFalse;
    }

    SetTimer (childWindow, 1, 250, nullptr);
    return kResultTrue;
#else
    (void)parent; (void)type;
    return kResultFalse;
#endif
}

tresult PLUGIN_API RouteProbeView::removed ()
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

tresult PLUGIN_API RouteProbeView::onSize (ViewRect* newSize)
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

LRESULT CALLBACK RouteProbeView::windowProc (HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    RouteProbeView* self = reinterpret_cast<RouteProbeView*> (GetWindowLongPtrW (hwnd, GWLP_USERDATA));
    if (msg == WM_NCCREATE)
    {
        auto* cs = reinterpret_cast<CREATESTRUCTW*> (lParam);
        self = static_cast<RouteProbeView*> (cs->lpCreateParams);
        SetWindowLongPtrW (hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR> (self));
    }

    return self ? self->handleMessage (hwnd, msg, wParam, lParam)
                : DefWindowProcW (hwnd, msg, wParam, lParam);
}

LRESULT RouteProbeView::handleMessage (HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
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

void RouteProbeView::paint (HWND hwnd)
{
    PAINTSTRUCT ps {};
    HDC dc = BeginPaint (hwnd, &ps);

    RECT client {};
    GetClientRect (hwnd, &client);
    HBRUSH bg = CreateSolidBrush (RGB (17, 21, 27));
    FillRect (dc, &client, bg);
    DeleteObject (bg);

    SetBkMode (dc, TRANSPARENT);
    SetTextColor (dc, RGB (231, 237, 244));

    HFONT titleFont = CreateFontW (-24, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
                                   DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                   CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
    HFONT bodyFont = CreateFontW (-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                                  DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                  CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
    HFONT monoFont = CreateFontW (-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                                  DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                                  CLEARTYPE_QUALITY, FIXED_PITCH, L"Consolas");

    auto oldFont = SelectObject (dc, titleFont);
    RECT r {18, 14, client.right - 18, 44};
    DrawTextW (dc, L"FIELD ROUTE PROBE", -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

    SelectObject (dc, bodyFont);
    SetTextColor (dc, RGB (137, 154, 173));
    r = {18, 45, client.right - 18, 80};
    DrawTextW (dc,
               L"Loaded on this mixer track. If 'All names observed' only shows this track, FL Studio is not exposing upstream routed-track names through VST3.",
               -1, &r, DT_LEFT | DT_WORDBREAK);

    const std::array<const wchar_t*, 10> labels {
        L"Current channel", L"All names observed", L"Context callbacks", L"Channel UID",
        L"Channel runtime ID", L"Channel index", L"Index namespace", L"Plugin location",
        L"Channel colour ARGB", L"Probe note"
    };

    const auto values = controller ? controller->getDisplayValues () : std::array<std::string, 10> {};

    int y = 88;
    for (size_t i = 0; i < labels.size (); ++i)
    {
        const int rowH = (i == 1 || i == 9) ? 48 : 30;

        RECT labelRect {18, y, 198, y + rowH};
        SelectObject (dc, bodyFont);
        SetTextColor (dc, i <= 1 ? RGB (95, 208, 194) : RGB (126, 142, 161));
        DrawTextW (dc, labels[i], -1, &labelRect, DT_LEFT | DT_TOP | DT_SINGLELINE);

        RECT valueRect {205, y, client.right - 18, y + rowH};
        SelectObject (dc, monoFont);
        SetTextColor (dc, RGB (224, 231, 239));
        const auto wide = utf8ToWide (values[i]);
        DrawTextW (dc, wide.c_str (), static_cast<int> (wide.size ()), &valueRect,
                   DT_LEFT | DT_TOP | DT_WORDBREAK | DT_NOPREFIX);

        HPEN pen = CreatePen (PS_SOLID, 1, RGB (39, 48, 60));
        auto oldPen = SelectObject (dc, pen);
        MoveToEx (dc, 18, y + rowH - 5, nullptr);
        LineTo (dc, client.right - 18, y + rowH - 5);
        SelectObject (dc, oldPen);
        DeleteObject (pen);

        y += rowH;
    }

    SelectObject (dc, oldFont);
    DeleteObject (titleFont);
    DeleteObject (bodyFont);
    DeleteObject (monoFont);
    EndPaint (hwnd, &ps);
}

#endif

} // namespace FieldRouteProbe
