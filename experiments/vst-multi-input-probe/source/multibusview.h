#pragma once

#include "public.sdk/source/common/pluginview.h"

#if SMTG_OS_WINDOWS
#include <windows.h>
#endif

namespace FieldMultiInputProbe {

class Controller;

class MultiBusView : public Steinberg::CPluginView
{
public:
    explicit MultiBusView (Controller* controller);
    ~MultiBusView () SMTG_OVERRIDE;

    Steinberg::tresult PLUGIN_API isPlatformTypeSupported (Steinberg::FIDString type) SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API attached (void* parent, Steinberg::FIDString type) SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API removed () SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API onSize (Steinberg::ViewRect* newSize) SMTG_OVERRIDE;

private:
#if SMTG_OS_WINDOWS
    static LRESULT CALLBACK windowProc (HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);
    LRESULT handleMessage (HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);
    void paint (HWND hwnd);
    HWND childWindow {nullptr};
#endif
    Controller* controller {nullptr};
};

} // namespace FieldMultiInputProbe
