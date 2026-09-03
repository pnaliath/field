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
constexpr int kBands = 24;
constexpr float kPi = 3.14159265358979323846f;

HINSTANCE gDllInstance = nullptr;

char gLongName[] = "Field V0.04 Visualizer";
char gShortName[] = "FieldV004";

TFruityPlugInfo gPluginInfo = {
    CurrentSDKVersion,
    gLongName,
    gShortName,
    0,
    0,
    0,
    0,
    0,
    {}
};

enum class EngineMode : int
{
    Bypass = 0,
    Field = 1,
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

struct DrawTrack
{
    const InputMetadata* meta = nullptr;
    float peakDb = -120.0f;
    float balance = 0.0f;
    float width = 0.0f;
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
    std::wstring out (static_cast<size_t> (needed), L'\0');
    MultiByteToWideChar (
        CP_ACP, 0, text.data (), static_cast<int> (text.size ()), out.data (), needed);
    return out;
}

float linearToDb (double linear)
{
    return static_cast<float> (20.0 * std::log10 (std::max (linear, 1.0e-6)));
}

float clamp01 (float v)
{
    return std::clamp (v, 0.0f, 1.0f);
}

COLORREF mixColor (COLORREF a, COLORREF b, float amountOfB)
{
    amountOfB = clamp01 (amountOfB);
    const float amountOfA = 1.0f - amountOfB;
    const int r = static_cast<int> (GetRValue (a) * amountOfA + GetRValue (b) * amountOfB);
    const int g = static_cast<int> (GetGValue (a) * amountOfA + GetGValue (b) * amountOfB);
    const int bl = static_cast<int> (GetBValue (a) * amountOfA + GetBValue (b) * amountOfB);
    return RGB (std::clamp (r, 0, 255), std::clamp (g, 0, 255), std::clamp (bl, 0, 255));
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
    rmsDb = linearToDb (rms);
    peakDb = linearToDb (peak);
}

class FieldV004Visualizer final : public TCPPFruityPlug
{
public:
    FieldV004Visualizer (int tag, TFruityPlugHost* host)
        : TCPPFruityPlug (tag, host, gDllInstance)
    {
        Info = &gPluginInfo;
        for (auto& p : routePeakDb)
            p.store (-120.0f, std::memory_order_relaxed);
        for (auto& p : routeBalance)
            p.store (0.0f, std::memory_order_relaxed);
        for (auto& p : routeWidth)
            p.store (0.0f, std::memory_order_relaxed);
        for (auto& route : routeSpectrum)
            for (auto& band : route)
                band.store (0.0f, std::memory_order_relaxed);
        updateBandCoefficients (44100.0f);
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
                    InvalidateRect (editorWindow, nullptr, FALSE);
                return 1;

            case FPD_SetSampleRate:
                if (value > 1000)
                {
                    sampleRate.store (static_cast<float> (value), std::memory_order_relaxed);
                    updateBandCoefficients (static_cast<float> (value));
                }
                break;

            default:
                break;
        }
        return TCPPFruityPlug::Dispatcher (id, index, value);
    }

    void _stdcall Idle_Public () override
    {
        if (++idleCounter >= 6)
        {
            idleCounter = 0;
            refreshMetadata ();
        }
        if (editorWindow)
            InvalidateRect (editorWindow, nullptr, FALSE);
    }

    void _stdcall Eff_Render (PWAV32FS source, PWAV32FS dest, int length) override
    {
        if (!dest || length <= 0)
            return;

        float refRms = -120.0f;
        float refPeak = -120.0f;
        analyseStereo (source, length, refRms, refPeak);
        referenceRmsDb.store (refRms, std::memory_order_relaxed);
        referencePeakDb.store (refPeak, std::memory_order_relaxed);

        const auto currentMode = static_cast<EngineMode> (mode.load (std::memory_order_relaxed));
        if (currentMode == EngineMode::Bypass)
        {
            liveRouteCount.store (0, std::memory_order_relaxed);
            reconstructRmsDb.store (-120.0f, std::memory_order_relaxed);
            reconstructPeakDb.store (-120.0f, std::memory_order_relaxed);
            nullRmsDb.store (-120.0f, std::memory_order_relaxed);
            nullPeakDb.store (-120.0f, std::memory_order_relaxed);
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
            if (source && source != dest)
                std::memcpy (dest, source, static_cast<size_t> (length) * sizeof (TWAV32FS));
            return;
        }

        std::memset (recon, 0, static_cast<size_t> (length) * sizeof (TWAV32FS));
        const int count = std::clamp (
            reportedRouteCount.load (std::memory_order_relaxed), 0, kMaxRoutes);
        for (int route = 0; route < count; ++route)
            routePeakDb[static_cast<size_t> (route)].store (-120.0f, std::memory_order_relaxed);

        int live = 0;
        const bool doSpectrum = ((++analysisBlockCounter & 1u) == 0u);

        for (int route = 1; route <= count; ++route)
        {
            TIOBuffer input {};
            PlugHost->GetInBuffer (HostTag, static_cast<intptr_t> (route), &input);
            if (!input.Buffer || (input.Flags & IO_Filled) == 0)
                continue;

            auto* routeBuffer = static_cast<PWAV32FS> (input.Buffer);
            const size_t routeArrayIndex = static_cast<size_t> (route - 1);
            double sumL2 = 0.0;
            double sumR2 = 0.0;
            double sumMid2 = 0.0;
            double sumSide2 = 0.0;
            double routePeak = 0.0;

            for (int i = 0; i < length; ++i)
            {
                const float l = routeBuffer[i][0];
                const float r = routeBuffer[i][1];
                recon[i][0] += l;
                recon[i][1] += r;
                const double dl = l;
                const double dr = r;
                const double mid = 0.5 * (dl + dr);
                const double side = 0.5 * (dl - dr);
                sumL2 += dl * dl;
                sumR2 += dr * dr;
                sumMid2 += mid * mid;
                sumSide2 += side * side;
                routePeak = std::max (routePeak, std::max (std::abs (dl), std::abs (dr)));
            }

            const double left = std::sqrt (sumL2 / std::max (1, length));
            const double right = std::sqrt (sumR2 / std::max (1, length));
            const double mid = std::sqrt (sumMid2 / std::max (1, length));
            const double side = std::sqrt (sumSide2 / std::max (1, length));
            const float balance = static_cast<float> (
                std::clamp ((right - left) / (right + left + 1.0e-12), -1.0, 1.0));
            const float width = clamp01 (static_cast<float> ((side / (mid + side + 1.0e-12)) * 1.65));

            routePeakDb[routeArrayIndex].store (linearToDb (routePeak), std::memory_order_relaxed);
            routeBalance[routeArrayIndex].store (balance, std::memory_order_relaxed);
            routeWidth[routeArrayIndex].store (width, std::memory_order_relaxed);
            if (doSpectrum)
                analyseSpectrum (routeArrayIndex, routeBuffer, length);
            ++live;
        }

        liveRouteCount.store (live, std::memory_order_relaxed);
        float reconRms = -120.0f;
        float reconPeak = -120.0f;
        analyseStereo (recon, length, reconRms, reconPeak);
        reconstructRmsDb.store (reconRms, std::memory_order_relaxed);
        reconstructPeakDb.store (reconPeak, std::memory_order_relaxed);

        if (currentMode == EngineMode::Field)
        {
            nullRmsDb.store (-120.0f, std::memory_order_relaxed);
            nullPeakDb.store (-120.0f, std::memory_order_relaxed);
            std::memcpy (dest, recon, static_cast<size_t> (length) * sizeof (TWAV32FS));
            return;
        }

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
        nullRmsDb.store (linearToDb (nullRms), std::memory_order_relaxed);
        nullPeakDb.store (linearToDb (nullPeak), std::memory_order_relaxed);
    }

private:
    static LRESULT CALLBACK windowProc (HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam)
    {
        auto* self = reinterpret_cast<FieldV004Visualizer*> (
            GetWindowLongPtrW (hwnd, GWLP_USERDATA));
        if (message == WM_NCCREATE)
        {
            auto* create = reinterpret_cast<CREATESTRUCTW*> (lParam);
            self = static_cast<FieldV004Visualizer*> (create->lpCreateParams);
            SetWindowLongPtrW (hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR> (self));
        }
        if (!self)
            return DefWindowProcW (hwnd, message, wParam, lParam);

        switch (message)
        {
            case WM_LBUTTONUP:
                self->handleClick (
                    static_cast<int> (static_cast<short> (LOWORD (lParam))),
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

    void updateBandCoefficients (float sr)
    {
        sr = std::max (sr, 8000.0f);
        const float minHz = 70.0f;
        const float maxHz = std::min (16000.0f, sr * 0.42f);
        const float logMin = std::log (minHz);
        const float logMax = std::log (maxHz);
        for (int band = 0; band < kBands; ++band)
        {
            const float t = (kBands == 1) ? 0.0f :
                static_cast<float> (band) / static_cast<float> (kBands - 1);
            const float hz = std::exp (logMin + t * (logMax - logMin));
            bandHz[static_cast<size_t> (band)].store (hz, std::memory_order_relaxed);
            const float omega = 2.0f * kPi * hz / sr;
            bandCoeff[static_cast<size_t> (band)].store (
                2.0f * std::cos (omega), std::memory_order_relaxed);
        }
    }

    void analyseSpectrum (size_t routeIndex, PWAV32FS buffer, int length)
    {
        if (!buffer || length <= 0 || routeIndex >= kMaxRoutes)
            return;
        for (int band = 0; band < kBands; ++band)
        {
            const float coeff = bandCoeff[static_cast<size_t> (band)].load (std::memory_order_relaxed);
            double s1 = 0.0;
            double s2 = 0.0;
            for (int i = 0; i < length; ++i)
            {
                const double mono = 0.5 * static_cast<double> (buffer[i][0] + buffer[i][1]);
                const double s0 = mono + static_cast<double> (coeff) * s1 - s2;
                s2 = s1;
                s1 = s0;
            }
            const double power = std::max (0.0,
                s1 * s1 + s2 * s2 - static_cast<double> (coeff) * s1 * s2);
            const double magnitude = (2.0 * std::sqrt (power)) / std::max (1, length);
            const float db = linearToDb (magnitude);
            const float normalized = clamp01 ((db + 72.0f) / 72.0f);
            auto& cell = routeSpectrum[routeIndex][static_cast<size_t> (band)];
            const float old = cell.load (std::memory_order_relaxed);
            cell.store (old * 0.72f + normalized * 0.28f, std::memory_order_relaxed);
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

    void clearActivity ()
    {
        for (auto& p : routePeakDb)
            p.store (-120.0f, std::memory_order_relaxed);
        liveRouteCount.store (0, std::memory_order_relaxed);
    }

    void handleClick (int x, int y)
    {
        if (y < 66 || y > 104)
            return;
        if (x >= 20 && x < 155)
        {
            mode.store (static_cast<int> (EngineMode::Bypass), std::memory_order_relaxed);
            clearActivity ();
        }
        else if (x >= 165 && x < 330)
            mode.store (static_cast<int> (EngineMode::Field), std::memory_order_relaxed);
        else if (x >= 340 && x < 485)
            mode.store (static_cast<int> (EngineMode::Null), std::memory_order_relaxed);
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
                wc.lpfnWndProc = &FieldV004Visualizer::windowProc;
                wc.hInstance = gDllInstance;
                wc.hCursor = LoadCursorW (nullptr, IDC_ARROW);
                wc.lpszClassName = L"FieldV004VisualizerWindow";
                RegisterClassExW (&wc);
                registered = true;
            }
            editorWindow = CreateWindowExW (
                0,
                L"FieldV004VisualizerWindow",
                L"",
                WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS,
                0, 0, 1180, 760,
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
        HPEN pen = CreatePen (PS_SOLID, 1, active ? RGB (91, 210, 195) : RGB (82, 96, 112));
        auto oldPen = SelectObject (dc, pen);
        auto oldBrush = SelectObject (dc, GetStockObject (NULL_BRUSH));
        Rectangle (dc, rect.left, rect.top, rect.right, rect.bottom);
        SelectObject (dc, oldBrush);
        SelectObject (dc, oldPen);
        DeleteObject (pen);
        SetTextColor (dc, active ? RGB (239, 248, 246) : RGB (190, 203, 217));
        RECT tr = rect;
        DrawTextW (dc, text, -1, &tr, DT_CENTER | DT_SINGLELINE | DT_VCENTER);
    }

    static int yForFrequency (float hz, int top, int bottom)
    {
        const float minHz = 70.0f;
        const float maxHz = 16000.0f;
        const float t = clamp01 ((std::log (std::max (hz, minHz)) - std::log (minHz)) /
                                 (std::log (maxHz) - std::log (minHz)));
        return bottom - static_cast<int> (t * static_cast<float> (bottom - top));
    }

    void drawFieldGrid (HDC dc, const RECT& area)
    {
        HPEN gridPen = CreatePen (PS_SOLID, 1, RGB (36, 44, 54));
        auto oldPen = SelectObject (dc, gridPen);
        const int center = (area.left + area.right) / 2;
        MoveToEx (dc, center, area.top, nullptr);
        LineTo (dc, center, area.bottom);
        const int quarter = (area.right - area.left) / 4;
        MoveToEx (dc, center - quarter, area.top, nullptr);
        LineTo (dc, center - quarter, area.bottom);
        MoveToEx (dc, center + quarter, area.top, nullptr);
        LineTo (dc, center + quarter, area.bottom);
        const std::array<float, 9> labels {
            70.0f, 120.0f, 250.0f, 500.0f, 1000.0f, 2000.0f, 5000.0f, 10000.0f, 16000.0f
        };
        for (float hz : labels)
        {
            const int y = yForFrequency (hz, area.top, area.bottom);
            MoveToEx (dc, area.left, y, nullptr);
            LineTo (dc, area.right, y);
        }
        SelectObject (dc, oldPen);
        DeleteObject (gridPen);
        SetTextColor (dc, RGB (93, 108, 124));
        SetBkMode (dc, TRANSPARENT);
        RECT lr {area.left, area.top - 24, area.right, area.top};
        DrawTextW (dc, L"LEFT                                      CENTER                                      RIGHT", -1,
                   &lr, DT_CENTER | DT_SINGLELINE | DT_VCENTER);
        for (float hz : labels)
        {
            wchar_t label[32] {};
            if (hz >= 1000.0f)
                swprintf_s (label, L"%.0fk", hz / 1000.0f);
            else
                swprintf_s (label, L"%.0f", hz);
            const int y = yForFrequency (hz, area.top, area.bottom);
            RECT fr {area.left - 48, y - 10, area.left - 6, y + 10};
            DrawTextW (dc, label, -1, &fr, DT_RIGHT | DT_SINGLELINE | DT_VCENTER);
        }
    }

    void drawSpectralBody (HDC dc, const DrawTrack& track, const RECT& area)
    {
        if (!track.meta)
            return;
        const int route = track.meta->routeIndex;
        if (route < 1 || route > kMaxRoutes)
            return;
        const size_t routeIndex = static_cast<size_t> (route - 1);
        const int centerBase = (area.left + area.right) / 2;
        const float halfSpan = static_cast<float> (area.right - area.left) * 0.40f;
        const int centerX = centerBase + static_cast<int> (track.balance * halfSpan);
        std::array<POINT, kBands * 2> points {};

        for (int band = 0; band < kBands; ++band)
        {
            const float energy = routeSpectrum[routeIndex][static_cast<size_t> (band)].load (std::memory_order_relaxed);
            const float hz = bandHz[static_cast<size_t> (band)].load (std::memory_order_relaxed);
            const int y = yForFrequency (hz, area.top, area.bottom);
            const float halfWidth = 5.0f + energy * (24.0f + track.width * 42.0f);
            points[static_cast<size_t> (band)] = {centerX - static_cast<int> (halfWidth), y};
            points[static_cast<size_t> (kBands * 2 - 1 - band)] = {centerX + static_cast<int> (halfWidth), y};
        }

        COLORREF raw = static_cast<COLORREF> (track.meta->color & 0x00FFFFFF);
        if (raw == RGB (0, 0, 0))
            raw = RGB (115, 160, 190);
        const COLORREF bg = RGB (16, 20, 26);
        const COLORREF fill = mixColor (raw, bg, 0.68f);
        const COLORREF outline = mixColor (raw, RGB (245, 250, 255), 0.20f);
        HBRUSH bodyBrush = CreateSolidBrush (fill);
        HPEN bodyPen = CreatePen (PS_SOLID, 2, outline);
        auto oldBrush = SelectObject (dc, bodyBrush);
        auto oldPen = SelectObject (dc, bodyPen);
        Polygon (dc, points.data (), static_cast<int> (points.size ()));
        SelectObject (dc, oldPen);
        SelectObject (dc, oldBrush);
        DeleteObject (bodyPen);
        DeleteObject (bodyBrush);

        HPEN spinePen = CreatePen (PS_SOLID, 1, mixColor (outline, bg, 0.25f));
        oldPen = SelectObject (dc, spinePen);
        MoveToEx (dc, centerX, area.top, nullptr);
        LineTo (dc, centerX, area.bottom);
        SelectObject (dc, oldPen);
        DeleteObject (spinePen);
    }

    void paint (HWND hwnd)
    {
        PAINTSTRUCT ps {};
        HDC dc = BeginPaint (hwnd, &ps);
        RECT client {};
        GetClientRect (hwnd, &client);
        const COLORREF bgColor = RGB (16, 20, 26);
        HBRUSH bg = CreateSolidBrush (bgColor);
        FillRect (dc, &client, bg);
        DeleteObject (bg);
        SetBkMode (dc, TRANSPARENT);

        HFONT titleFont = CreateFontW (-25, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        HFONT bodyFont = CreateFontW (-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        HFONT smallFont = CreateFontW (-14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        HFONT monoFont = CreateFontW (-14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, FIXED_PITCH, L"Consolas");

        auto oldFont = SelectObject (dc, titleFont);
        SetTextColor (dc, RGB (232, 238, 245));
        RECT r {20, 10, client.right - 20, 42};
        DrawTextW (dc, L"FIELD V0.04 - LIVE OBJECT MIX VISUALIZER", -1, &r,
                   DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        SelectObject (dc, bodyFont);
        SetTextColor (dc, RGB (135, 154, 174));
        r = {20, 38, client.right - 20, 64};
        DrawTextW (dc,
            L"One FL-native instance. Routed mixer tracks become live spectral bodies; names, colors and audio update from FL Studio.",
            -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);

        const auto currentMode = static_cast<EngineMode> (mode.load (std::memory_order_relaxed));
        drawButton (dc, RECT {20, 68, 155, 104}, L"BYPASS", currentMode == EngineMode::Bypass);
        drawButton (dc, RECT {165, 68, 330, 104}, L"START FIELD", currentMode == EngineMode::Field);
        drawButton (dc, RECT {340, 68, 485, 104}, L"NULL CHECK", currentMode == EngineMode::Null);

        SelectObject (dc, monoFont);
        SetTextColor (dc, RGB (91, 210, 195));
        wchar_t status[320] {};
        swprintf_s (
            status,
            L"REF %.1f/%.1f dB    FIELD %.1f/%.1f dB    NULL %.1f/%.1f dB    routes %d    live %d    SR %.0f",
            referenceRmsDb.load (std::memory_order_relaxed),
            referencePeakDb.load (std::memory_order_relaxed),
            reconstructRmsDb.load (std::memory_order_relaxed),
            reconstructPeakDb.load (std::memory_order_relaxed),
            nullRmsDb.load (std::memory_order_relaxed),
            nullPeakDb.load (std::memory_order_relaxed),
            reportedRouteCount.load (std::memory_order_relaxed),
            liveRouteCount.load (std::memory_order_relaxed),
            sampleRate.load (std::memory_order_relaxed));
        r = {505, 70, client.right - 20, 103};
        DrawTextW (dc, status, -1, &r, DT_RIGHT | DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);

        const int sidebarLeft = 20;
        const int sidebarRight = 220;
        const int fieldLeft = 285;
        const int fieldTop = 146;
        const int fieldBottom = static_cast<int> (client.bottom) - 28;
        const int fieldRight = static_cast<int> (client.right) - 22;
        RECT fieldArea {fieldLeft, fieldTop, fieldRight, fieldBottom};

        SelectObject (dc, smallFont);
        drawFieldGrid (dc, fieldArea);

        std::vector<DrawTrack> active;
        active.reserve (inputs.size ());
        for (const auto& item : inputs)
        {
            if (item.routeIndex < 1 || item.routeIndex > kMaxRoutes)
                continue;
            const size_t idx = static_cast<size_t> (item.routeIndex - 1);
            const float peak = routePeakDb[idx].load (std::memory_order_relaxed);
            if (peak <= -72.0f)
                continue;
            DrawTrack d;
            d.meta = &item;
            d.peakDb = peak;
            d.balance = routeBalance[idx].load (std::memory_order_relaxed);
            d.width = routeWidth[idx].load (std::memory_order_relaxed);
            active.push_back (d);
        }

        std::sort (active.begin (), active.end (), [] (const DrawTrack& a, const DrawTrack& b)
        {
            return a.peakDb < b.peakDb;
        });
        for (const auto& track : active)
            drawSpectralBody (dc, track, fieldArea);

        SelectObject (dc, bodyFont);
        SetTextColor (dc, RGB (111, 126, 143));
        r = {sidebarLeft, 118, sidebarRight, 144};
        DrawTextW (dc, L"ACTIVE TRACKS", -1, &r, DT_LEFT | DT_SINGLELINE | DT_VCENTER);

        const int maxRows = std::max (0, (static_cast<int> (client.bottom) - 160) / 28);
        std::vector<DrawTrack> loudest = active;
        std::sort (loudest.begin (), loudest.end (), [] (const DrawTrack& a, const DrawTrack& b)
        {
            return a.peakDb > b.peakDb;
        });

        SelectObject (dc, smallFont);
        for (int i = 0; i < static_cast<int> (loudest.size ()) && i < maxRows; ++i)
        {
            const auto& track = loudest[static_cast<size_t> (i)];
            const auto& item = *track.meta;
            const int y = 150 + i * 28;
            COLORREF raw = static_cast<COLORREF> (item.color & 0x00FFFFFF);
            if (raw == RGB (0, 0, 0))
                raw = RGB (115, 160, 190);
            RECT swatch {sidebarLeft, y + 5, sidebarLeft + 14, y + 19};
            HBRUSH colorBrush = CreateSolidBrush (raw);
            FillRect (dc, &swatch, colorBrush);
            DeleteObject (colorBrush);
            std::string display = !item.visibleName.empty () ? item.visibleName : item.userName;
            if (display.empty ())
                display = "(unnamed)";
            const auto wide = ansiToWide (display);
            RECT nameRect {sidebarLeft + 22, y, sidebarRight - 48, y + 26};
            SetTextColor (dc, RGB (207, 218, 229));
            DrawTextW (dc, wide.c_str (), -1, &nameRect,
                       DT_LEFT | DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);
            wchar_t peakText[32] {};
            swprintf_s (peakText, L"%.0f", track.peakDb);
            RECT peakRect {sidebarRight - 45, y, sidebarRight, y + 26};
            SetTextColor (dc, RGB (119, 219, 160));
            DrawTextW (dc, peakText, -1, &peakRect, DT_RIGHT | DT_SINGLELINE | DT_VCENTER);
        }

        if (currentMode == EngineMode::Bypass)
        {
            SelectObject (dc, titleFont);
            SetTextColor (dc, RGB (187, 199, 212));
            RECT message {fieldArea.left + 40, fieldArea.top + 80, fieldArea.right - 40, fieldArea.top + 160};
            DrawTextW (dc, L"PRESS START FIELD TO READ INDIVIDUAL ROUTED TRACK BUFFERS", -1, &message,
                       DT_CENTER | DT_WORDBREAK | DT_VCENTER);
            SelectObject (dc, bodyFont);
            SetTextColor (dc, RGB (116, 133, 151));
            RECT sub {fieldArea.left + 80, fieldArea.top + 155, fieldArea.right - 80, fieldArea.top + 215};
            DrawTextW (dc,
                L"BYPASS is a safe transparent pass-through. START FIELD reconstructs the same mix from individual tracks and drives these objects from the actual post-mixer audio.",
                -1, &sub, DT_CENTER | DT_WORDBREAK);
        }
        else if (active.empty ())
        {
            SelectObject (dc, bodyFont);
            SetTextColor (dc, RGB (245, 166, 91));
            RECT message {fieldArea.left + 40, fieldArea.top + 80, fieldArea.right - 40, fieldArea.top + 160};
            DrawTextW (dc, L"FIELD IS RUNNING, BUT NO ROUTED BUFFER IS CURRENTLY ABOVE -72 dB.", -1,
                       &message, DT_CENTER | DT_WORDBREAK | DT_VCENTER);
        }

        SelectObject (dc, oldFont);
        DeleteObject (titleFont);
        DeleteObject (bodyFont);
        DeleteObject (smallFont);
        DeleteObject (monoFont);
        EndPaint (hwnd, &ps);
    }

    HWND editorWindow = nullptr;
    int idleCounter = 0;
    unsigned int analysisBlockCounter = 0;
    std::vector<InputMetadata> inputs;
    std::atomic<int> mode {static_cast<int> (EngineMode::Bypass)};
    std::atomic<int> reportedRouteCount {0};
    std::atomic<int> liveRouteCount {0};
    std::atomic<float> sampleRate {44100.0f};
    std::atomic<float> referenceRmsDb {-120.0f};
    std::atomic<float> referencePeakDb {-120.0f};
    std::atomic<float> reconstructRmsDb {-120.0f};
    std::atomic<float> reconstructPeakDb {-120.0f};
    std::atomic<float> nullRmsDb {-120.0f};
    std::atomic<float> nullPeakDb {-120.0f};
    std::array<std::atomic<float>, kMaxRoutes> routePeakDb;
    std::array<std::atomic<float>, kMaxRoutes> routeBalance;
    std::array<std::atomic<float>, kMaxRoutes> routeWidth;
    std::array<std::array<std::atomic<float>, kBands>, kMaxRoutes> routeSpectrum;
    std::array<std::atomic<float>, kBands> bandCoeff;
    std::array<std::atomic<float>, kBands> bandHz;
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
    return new FieldV004Visualizer (tag, host);
}
