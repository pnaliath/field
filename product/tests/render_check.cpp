#include "FieldView.h"
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <fstream>
void check(bool x,const char* message){if(!x)throw std::runtime_error(message);}
void paint(field::View& view){InvalidateRect(view.window(),nullptr,FALSE);UpdateWindow(view.window());}
void mouse(field::View& view,UINT type,int x,int y){SendMessageW(view.window(),type,type==WM_MOUSEMOVE?MK_LBUTTON:0,MAKELPARAM(x,y));}
bool capture(field::View& view,const wchar_t* path){
    return view.saveImage(path);
}
int main(){try{
    auto engine=std::make_unique<field::Engine>();engine->setRate(48000);
    const char* names[]={"Kick","Bass","Vocal","Guitar L","Guitar R","Wide pad","Hi-hat","Reverb","Delay"};
    float frequencies[]={60,100,800,420,600,1800,9000,1600,1200};
    for(int i=0;i<9;++i)engine->setRoute(i,i+1,names[i],i==7?field::Kind::Reverb:i==8?field::Kind::Delay:field::Kind::Source);
    HWND parent=CreateWindowW(L"STATIC",L"Field renderer validation",WS_OVERLAPPEDWINDOW|WS_VISIBLE,0,0,1240,840,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
    field::View view(*engine,GetModuleHandleW(nullptr));check(view.attach(parent),"create native Windows editor");
    auto p=engine->preferences();p.selected=2;engine->setPreferences(p);
    for(int block=0;block<90;++block){for(int r=0;r<9;++r){std::array<float,768> l{},rr{};
        for(int i=0;i<768;++i){double t=(block*768+i)/48000.;float v=float(.18*std::sin(t*frequencies[r]*6.283185307));
            if(r==2)v+=float(.06*std::sin(t*2200*6.283185307));l[i]=r==4?0:v;rr[i]=r==3?0:r==5?float(.18*std::sin(t*2131*6.283185307)):v;}
        engine->capture(r,l.data(),rr.data(),768);}
        MSG msg;while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){TranslateMessage(&msg);DispatchMessageW(&msg);}Sleep(16);}
    paint(view);check(view.renderedRoute(3)&&view.renderedRoutePan(3)<-.99f,"actual renderer hard-left pan");
    check(!view.renderedRoute(7)&&!view.renderedRoute(8),"reverb and delay returns must remain auxiliary particle fields, not source bodies");
    check(capture(view,L"Field-full-range.png"),"full range screenshot");
    mouse(view,WM_LBUTTONDOWN,1160,148);mouse(view,WM_MOUSEMOVE,1160,300);mouse(view,WM_LBUTTONUP,1160,300);
    mouse(view,WM_LBUTTONDOWN,1160,654);mouse(view,WM_MOUSEMOVE,1160,500);mouse(view,WM_LBUTTONUP,1160,500);
    paint(view);p=engine->preferences();check(p.frequency.low>.25f&&p.frequency.high<.75f,"frequency range handles change persisted range");
    check(!view.renderedRoute(0)&&!view.renderedRoute(6),"frequency range excludes low kick and high hat geometry");
    check(capture(view,L"Field-frequency-zoom.png"),"zoom screenshot");
    auto state=engine->save();auto restored=std::make_unique<field::Engine>();restored->stop();check(restored->restore(state.data(),state.size()),"zoom state from real UI loads");
    check(std::abs(restored->preferences().frequency.low-p.frequency.low)<.001,"UI zoom survives project reopen");
    mouse(view,WM_LBUTTONDOWN,1160,400);mouse(view,WM_MOUSEMOVE,1160,425);mouse(view,WM_LBUTTONUP,1160,425);
    check(engine->preferences().frequency.low<p.frequency.low,"dragging selected band pans the frequency window");
    mouse(view,WM_LBUTTONDBLCLK,1160,400);paint(view);check(engine->preferences().frequency.low==0&&engine->preferences().frequency.high==1,"double click resets frequency range");
    mouse(view,WM_LBUTTONDOWN,215,86);mouse(view,WM_LBUTTONUP,215,86);paint(view);check(engine->preferences().sidebarCollapsed,"sidebar collapse persists");
    mouse(view,WM_LBUTTONDOWN,1190,32);mouse(view,WM_LBUTTONUP,1190,32);paint(view);
    SendMessageW(view.window(),WM_KEYDOWN,VK_ESCAPE,0);paint(view);check(GetParent(view.window())==parent,"fullscreen escape restores original host parent");
    auto before=engine->preferences();mouse(view,WM_LBUTTONDOWN,550,430);mouse(view,WM_MOUSEMOVE,585,435);mouse(view,WM_LBUTTONUP,585,435);paint(view);
    check(std::abs(engine->preferences().yaw-before.yaw)>.1f,"camera drag remains functional");
    std::cout<<"PASS: Windows renderer pan, auxiliary reverb/delay, frequency handle drag, range pan, reset, state reopen, sidebar, fullscreen restore, orbit\n";
    std::cout<<"Last paint ms: "<<view.framePaintMs()<<"\n";
    return 0;
}catch(const std::exception& e){std::cerr<<"FAIL: "<<e.what()<<"\n";return 1;}}