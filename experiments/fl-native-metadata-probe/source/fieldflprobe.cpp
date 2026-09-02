#include "fp_cplug.h"

#include <windows.h>

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

namespace {

HINSTANCE gDllInstance = nullptr;

char gLongName[] = "Field FL Metadata Probe";
char gShortName[] = "FieldMeta";

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

class FieldFLMetadataProbe final : public TCPPFruityPlug
{
public:
    FieldFLMetadataProbe (int tag, TFruityPlugHost* host)
        : TCPPFruityPlug (tag, host, gDllInstance)
    {
        Info = &gPluginInfo;
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
        // Metadata-only diagnostic. The insert's normal audio is bit-transparent;
        // routed sidechain inputs are deliberately NOT summed into output.
        if (!source || !dest || length <= 0 || source == dest)
            return;
        std::memcpy (dest, source, static_cast<size_t> (length) * sizeof (TWAV32FS));
    }

private:
    static LRESULT CALLBACK windowProc (HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam)
    {
        auto* self = reinterpret_cast<FieldFLMetadataProbe*> (
            GetWindowLongPtrW (hwnd, GWLP_USERDATA));

        if (message == WM_NCCREATE)
        {
            auto* create = reinterpret_cast<CREATESTRUCTW*> (lParam);
            self = static_cast<FieldFLMetadataProbe*> (create->lpCreateParams);
            SetWindowLongPtrW (hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR> (self));
        }

        if (!self)
            return DefWindowProcW (hwnd, message, wParam, lParam);

        switch (message)
        {
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
        const int count = std::clamp (static_cast<int> (countResult), 0, 128);

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
                wc.lpfnWndProc = &FieldFLMetadataProbe::windowProc;
                wc.hInstance = gDllInstance;
                wc.hCursor = LoadCursorW (nullptr, IDC_ARROW);
                wc.lpszClassName = L"FieldFLMetadataProbeWindow";
                RegisterClassExW (&wc);
                registered = true;
            }

            editorWindow = CreateWindowExW (
                0,
                L"FieldFLMetadataProbeWindow",
                L"",
                WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS,
                0, 0, 820, 520,
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
        RECT r {20, 14, client.right - 20, 46};
        DrawTextW (dc, L"FIELD — FL NATIVE INPUT METADATA PROBE", -1, &r,
                   DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        SelectObject (dc, bodyFont);
        SetTextColor (dc, RGB (143, 160, 178));
        r = {20, 48, client.right - 20, 88};
        DrawTextW (dc,
                   L"Reads FL Studio native route metadata. Each row is an input route reaching this single plugin instance.",
                   -1, &r, DT_LEFT | DT_WORDBREAK);

        SelectObject (dc, monoFont);
        SetTextColor (dc, RGB (91, 210, 195));
        wchar_t countText[128] {};
        swprintf_s (countText, L"Host reports %d routed input(s)", static_cast<int> (inputs.size ())); 
        r = {20, 90, client.right - 20, 118};
        DrawTextW (dc, countText, -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        const int startY = 126;
        const int rowHeight = 43;

        SelectObject (dc, bodyFont);
        SetTextColor (dc, RGB (111, 126, 143));
        r = {20, startY - 25, client.right - 20, startY};
        DrawTextW (dc, L"ROUTE     COLOR     MIXER INDEX     VISIBLE / USER NAME", -1, &r,
                   DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        for (size_t i = 0; i < inputs.size (); ++i)
        {
            const auto& item = inputs[i];
            const int y = startY + static_cast<int> (i) * rowHeight;
            if (y + rowHeight > client.bottom - 16)
                break;

            HPEN linePen = CreatePen (PS_SOLID, 1, RGB (39, 48, 59));
            auto oldPen = SelectObject (dc, linePen);
            MoveToEx (dc, 20, y + rowHeight - 2, nullptr);
            LineTo (dc, client.right - 20, y + rowHeight - 2);
            SelectObject (dc, oldPen);
            DeleteObject (linePen);

            wchar_t routeText[32] {};
            swprintf_s (routeText, L"%d", item.routeIndex);
            RECT routeRect {20, y, 72, y + 34};
            SetTextColor (dc, RGB (222, 229, 237));
            DrawTextW (dc, routeText, -1, &routeRect, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

            RECT swatch {78, y + 7, 110, y + 29};
            HBRUSH colorBrush = CreateSolidBrush (static_cast<COLORREF> (item.color & 0x00FFFFFF));
            FillRect (dc, &swatch, colorBrush);
            DeleteObject (colorBrush);
            FrameRect (dc, &swatch, static_cast<HBRUSH> (GetStockObject (GRAY_BRUSH)));

            wchar_t indexText[32] {};
            swprintf_s (indexText, L"%d", item.mixerIndex);
            RECT indexRect {126, y, 226, y + 34};
            SetTextColor (dc, RGB (222, 229, 237));
            DrawTextW (dc, indexText, -1, &indexRect, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

            std::string display;
            if (!item.visibleName.empty ())
                display = item.visibleName;
            if (!item.userName.empty () && item.userName != item.visibleName)
                display += (display.empty () ? "" : " / ") + item.userName;
            if (display.empty ())
                display = "(unnamed)";

            const auto wide = ansiToWide (display);
            RECT nameRect {238, y, client.right - 142, y + 34};
            SetTextColor (dc, RGB (207, 218, 229));
            DrawTextW (dc, wide.c_str (), -1, &nameRect,
                       DT_LEFT | DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);

            wchar_t rawColor[48] {};
            swprintf_s (rawColor, L"0x%08X", static_cast<unsigned int> (item.color));
            RECT rawRect {client.right - 132, y, client.right - 20, y + 34};
            SetTextColor (dc, RGB (124, 139, 156));
            DrawTextW (dc, rawColor, -1, &rawRect, DT_RIGHT | DT_SINGLELINE | DT_VCENTER);
        }

        if (inputs.empty ())
        {
            SelectObject (dc, bodyFont);
            SetTextColor (dc, RGB (245, 166, 91));
            r = {20, 150, client.right - 20, 205};
            DrawTextW (dc,
                       L"No routed inputs reported. Create mixer routes or sidechains into this track, then change routing or reopen the editor.",
                       -1, &r, DT_LEFT | DT_WORDBREAK);
        }

        SelectObject (dc, oldFont);
        DeleteObject (titleFont);
        DeleteObject (bodyFont);
        DeleteObject (monoFont);
        EndPaint (hwnd, &ps);
    }

    HWND editorWindow = nullptr;
    std::vector<InputMetadata> inputs;
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
    return new FieldFLMetadataProbe (tag, host);
}
