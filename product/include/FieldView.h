#pragma once
#include "FieldCore.h"
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <objidl.h>
#include <gdiplus.h>
#include <functional>
#include <cstdio>

namespace field {
class View {
public:
    View(Engine& e,HINSTANCE module):engine(e),instance(module){}
    ~View();
    bool attach(HWND parent);
    void resize(int w,int h);
    HWND window() const{return hwnd;}
    std::function<void()> onIdle,onChange;
    std::wstring mode=L"FL Native";
private:
    Engine& engine;HINSTANCE instance;HWND hwnd=nullptr;ULONG_PTR gdiplus=0;
    Preferences prefs;Snapshot frame;
    bool dragging=false,moved=false,diagnostics=false;
    POINT last{};int scroll=0;std::vector<int> rows;
    FILE* log=nullptr;double lastPaint=0,lastLog=0,paintMs=0,fps=0;
    struct Rendered {bool drawn=false;float pan=0,width=0,z=0,low=0,high=0,dominant=0,presence=0;double delay=-1;};
    std::array<Rendered,Routes> rendered{};
    std::array<uint32_t,Routes> visibleOnset{};
    std::array<double,Routes> visibleDelay{};
    std::vector<Gdiplus::RectF> labelRects;
    static LRESULT CALLBACK proc(HWND,UINT,WPARAM,LPARAM);
    LRESULT message(UINT,WPARAM,LPARAM);
    void paint();void click(int,int);void menu(int,int,int);void exportLog();void writeLog();
    Gdiplus::PointF project(float x,float y,float z,const RECT& room) const;
    void body(Gdiplus::Graphics&,const RouteView&,int,const RECT&,float,float,float,float,const std::array<float,Bands>&,int);
    void savePrefs(){engine.setPreferences(prefs);if(onChange)onChange();}
};
}
