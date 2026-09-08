#include "fp_cplug.h"
#include "FieldView.h"
#include <cctype>

namespace {
HINSTANCE module=nullptr;
char name[]="Field 1",shortName[]="Field1Beta";
TFruityPlugInfo info={CurrentSDKVersion,name,shortName,FPF_Type_Effect|FPF_CantSmartDisable,0,0,0,0,{}};
field::Kind inferredKind(const std::string& title){
    std::string s;for(unsigned char c:title)if(!std::isspace(c)||!s.empty())s.push_back(char(std::toupper(c)));
    while(!s.empty()&&std::isspace(static_cast<unsigned char>(s.back())))s.pop_back();
    if(s=="REV"||s=="REVERB"||s=="FX REV"||s=="FX REVERB")return field::Kind::Reverb;
    if(s=="DEL"||s=="DELAY"||s=="ECHO"||s=="FX DEL"||s=="FX DELAY")return field::Kind::Delay;
    return field::Kind::Unknown;
}
class Native final:public TCPPFruityPlug {
    std::unique_ptr<field::Engine> engine;
    std::unique_ptr<field::View> view;
    std::atomic<int> routeCount{0};
    double lastMetadata=0;
    std::array<uint64_t,field::Routes> routeIds{};
    void metadata(){
        double now=field::nowMs();if(now-lastMetadata<250)return;lastMetadata=now;
        int count=int(std::clamp<intptr_t>(PlugHost->Dispatcher(HostTag,FHD_GetNumInOut,0,0),0,field::Routes));
        for(int i=0;i<count;++i){TNameColor nc{};bool valid=PlugHost->Dispatcher(HostTag,FHD_GetInName,i+1,reinterpret_cast<intptr_t>(&nc))!=0;
            uint64_t id=valid&&nc.Index>=0?uint64_t(nc.Index)+1:0x10000u+uint64_t(i);
            const char* n=valid?(nc.VisName[0]?nc.VisName:nc.Name):nullptr;
            std::string title;if(n){size_t len=0;while(len<sizeof(nc.Name)&&n[len])++len;title.assign(n,len);}
            if(title.empty())title="Route "+std::to_string(i+1);
            engine->setRoute(i,id,title,inferredKind(title));routeIds[i]=id;
        }
        for(int i=count;i<field::Routes;++i)if(routeIds[i]){engine->removeRoute(i);routeIds[i]=0;}
        routeCount.store(count,std::memory_order_release);
    }
public:
    Native(int tag,TFruityPlugHost* host):TCPPFruityPlug(tag,host,module),engine(std::make_unique<field::Engine>()){
        Info=&info;PlugHost->Dispatcher(HostTag,FHD_WantIdle,0,2);metadata();}
    void _stdcall DestroyObject() override {view.reset();engine.reset();TCPPFruityPlug::DestroyObject();}
    intptr_t _stdcall Dispatcher(intptr_t id,intptr_t index,intptr_t value) override {
        try{switch(id){case FPD_ShowEditor:
            if(value){if(!view){view=std::make_unique<field::View>(*engine,module);view->onIdle=[this]{metadata();};
                    view->onChange=[this]{PlugHost->Dispatcher(HostTag,FHD_SetDirty,0,0);};
                    if(!view->attach(reinterpret_cast<HWND>(value))){view.reset();return 0;}EditorHandle=view->window();}
                ShowWindow(view->window(),SW_SHOW);}else{view.reset();EditorHandle=nullptr;}return 1;
            case FPD_SetSampleRate:engine->setRate(double(value));break;
            case FPD_RoutingChanged:lastMetadata=0;metadata();return 1;
            case FPD_Flush:engine->flush();return 1;
            default:break;}
        }catch(...){return 0;}return TCPPFruityPlug::Dispatcher(id,index,value);
    }
    void _stdcall Idle_Public() override {try{metadata();}catch(...){}}
    void _stdcall Eff_Render(PWAV32FS source,PWAV32FS dest,int length) override {
        if(!dest||length<=0)return;double start=field::nowMs();
        // The master signal is authoritative, including all upstream master effects.
        field::passthrough(source?&source[0][0]:nullptr,&dest[0][0],length*2);
        try{int count=routeCount.load(std::memory_order_acquire);
            for(int r=0;r<count;++r){TIOBuffer input{};PlugHost->GetInBuffer(HostTag,r+1,&input);
                if(input.Buffer&&(input.Flags&IO_Filled)){auto p=static_cast<PWAV32FS>(input.Buffer);engine->capture(r,&p[0][0],&p[0][1],length,2);}}
        }catch(...){/* Output already contains the exact host input. */}
        engine->callbackMs.store(field::nowMs()-start,std::memory_order_relaxed);
    }
    void _stdcall SaveRestoreState(IStream* stream,BOOL save) override {
        if(!stream)return;try{ULONG actual=0;uint32_t size=0;
            if(save){auto data=engine->save();size=uint32_t(data.size());if(FAILED(stream->Write(&size,4,&actual))||actual!=4)return;
                stream->Write(data.data(),size,&actual);
            }else{if(FAILED(stream->Read(&size,4,&actual))||actual!=4||size>128000)return;
                std::vector<uint8_t> data(size);if(SUCCEEDED(stream->Read(data.data(),size,&actual))&&actual==size)engine->restore(data.data(),size);}
        }catch(...){}}
};
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)module=instance;return TRUE;}
extern "C" __declspec(dllexport) TFruityPlug* _stdcall CreatePlugInstance(TFruityPlugHost* host,int tag){
    try{return new Native(tag,host);}catch(...){return nullptr;}}
