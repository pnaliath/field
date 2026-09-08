#include "FieldCore.h"
#include <iostream>
#include <stdexcept>
#include <limits>
using namespace field;
void check(bool value,const char* why){if(!value)throw std::runtime_error(why);}
void advance(Engine& e){std::this_thread::sleep_for(std::chrono::milliseconds(17));e.tickForTest();}
int main(){try{
    auto e=std::make_unique<Engine>();e->stop();e->setRate(48000);
    e->setRoute(0,101,"Click");advance(*e);
    float click[64]{};click[20]=.5f;float zero[1024]{};
    e->capture(0,click,click,64);advance(*e);
    auto v=e->snapshot().routes[0];check(v.onsetCount>0&&v.provisional,"short first click must have a provisional body");
    for(int i=0;i<5;++i){e->capture(0,zero,zero,64);advance(*e);}
    check(e->snapshot().routes[0].provisional,"silence after a one-shot must not erase its shape");
    e->setRoute(1,102,"Reverb",Kind::Reverb);e->setKind(1,Kind::Source);e->setRoute(1,102,"Reverb",Kind::Reverb);
    check(e->snapshot().routes[1].kind==Kind::Source,"native metadata must respect the manual source override");
    e->setRoute(2,103,"Mono");advance(*e);float tone[1024],scaled[1024];
    for(int block=0;block<20;++block){for(int i=0;i<1024;++i)tone[i]=.2f*std::sin((block*1024+i)*.1308997f);
        e->capture(2,tone,tone,1024);advance(*e);}
    e->capture(2,tone,zero,1024);advance(*e);v=e->snapshot().routes[2];
    check(v.sustained&&renderedPan(v)<-.99f,"sustained rendered pan must follow the current channel balance");
    check(v.width<.001f,"panning mono must not introduce stereo width");
    e->setRoute(3,104,"Panned mono");e->setRoute(4,105,"Anti phase");advance(*e);
    for(int i=0;i<1024;++i)scaled[i]=tone[i]*.2f;
    e->capture(3,tone,scaled,1024);for(int i=0;i<1024;++i)scaled[i]=-tone[i];e->capture(4,tone,scaled,1024);advance(*e);
    check(e->snapshot().routes[3].width<.001f,"unequal channel gains must retain mono identity");
    check(e->snapshot().routes[4].width>.99f,"anti-phase content must retain stereo identity");
    check(spectralRadius(1,1)>spectralRadius(1,0)*4,"mono and stereo must have clearly distinct rendered width");
    Snapshot frame;frame.routes[0]=e->snapshot().routes[2];frame.routes[1].id=222;frame.routes[1].kind=Kind::Reverb;
    frame.routes[1].fxSource=0;frame.routes[1].fxConfidence=.4f;
    check(!associatedReturn(frame.routes[1],frame),"uncertain return cannot suppress an independent body");
    frame.routes[1].fxConfidence=.99f;check(associatedReturn(frame.routes[1],frame),"verified return can collapse into its source");
    frame.routes[0].visible=false;check(!associatedReturn(frame.routes[1],frame),"hidden parent cannot swallow an audible return");
    auto p=e->preferences();p.frequency={.22f,.64f};p.sidebarCollapsed=true;p.showAllRoutes=true;e->setPreferences(p);
    auto before=e->snapshot().routes[2];auto saved=e->save();auto restored=std::make_unique<Engine>();restored->stop();
    check(restored->restore(saved.data(),saved.size()),"version 3 project state roundtrip");
    check(std::abs(restored->preferences().frequency.low-.22f)<1.e-5f&&restored->preferences().sidebarCollapsed&&restored->preferences().showAllRoutes,"frequency range and UI controls must persist");
    restored->setRoute(1,102,"Reverb",Kind::Reverb);check(restored->snapshot().routes[1].kind==Kind::Source,"manual type must persist across project reopen");
    check(e->snapshot().routes[2].shape==before.shape&&e->snapshot().routes[2].z==before.z,"frequency zoom cannot modify measured source data");
    FrequencyRange range{.2f,.6f};range.move(.1f);check(std::abs(range.low-.3f)<1.e-5f,"range drag pans the frequency window");
    range.zoom(.5f,.5f);check(std::abs(range.high-range.low-.2f)<1.e-5f,"range wheel zoom narrows the window");
    check(std::abs(range.project(range.low))<1.e-5f&&std::abs(range.project(range.high)-1)<1.e-5f,"selected bounds fill the vertical axis");
    range={.99f,.01f};range.sanitize();check(range.high<=1&&range.high-range.low>=MinFrequencySpan-1.e-5f,"invalid ranges must remain bounded");
    std::cout<<"PASS: short one-shots, live pan, pan-independent width, manual overrides, safe FX suppression, frequency zoom and state persistence\n";
    return 0;
}catch(const std::exception& e){std::cerr<<"FAIL: "<<e.what()<<"\n";return 1;}}
