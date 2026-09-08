#include <windows.h>
#include "fp_plugclass.h"
#include <array>
#include <vector>
#include <memory>
#include <cstring>
#include <cstdio>
#include <iostream>
#include <random>
#include <stdexcept>
#include <chrono>
void check(bool v,const char* message){if(!v)throw std::runtime_error(message);}
class Host final:public TFruityPlugHost {
public:
    int routeCount=64;
    char programPath[MAX_PATH]="C:\\FieldNativeTest";
    std::array<std::array<float,8192>,128> routes{};
    Host(){HostVersion=21000000;Flags=0;AppHandle=nullptr;std::memset(WaveTables,0,sizeof(WaveTables));std::memset(TempBuffers,0,sizeof(TempBuffers));std::memset(Reserved,0,sizeof(Reserved));
        for(auto& r:routes)r.fill(.11f);}
    intptr_t _stdcall Dispatcher(TPluginTag Sender, intptr_t ID, intptr_t Index, intptr_t Value) override {
        if(ID==FHD_GetPath)return reinterpret_cast<intptr_t>(programPath);
        if(ID==FHD_GetNumInOut)return routeCount;
        if(ID==FHD_GetInName&&Index>=1&&Index<=routeCount){auto* nc=reinterpret_cast<TNameColor*>(Value);*nc=TNameColor{};
            nc->Index=int(Index);std::snprintf(nc->Name,sizeof(nc->Name),"Source %d",int(Index));return 1;}
        return 0;
    }
    void _stdcall OnParamChanged(TPluginTag Sender, int Index, int Value) override {}
    void _stdcall OnHint(TPluginTag Sender, char *Text) override {}
    void _stdcall ComputeLRVol_Old(float &LVol, float &RVol, int Pan, float Volume) override {}
    void _stdcall Voice_Release(intptr_t Sender) override {}
    void _stdcall Voice_Kill(intptr_t Sender, BOOL KillHandle) override {}
    int _stdcall Voice_ProcessEvent(intptr_t Sender, intptr_t EventID, intptr_t EventValue, intptr_t Flags) override {return {};}
    void _stdcall LockMix_Old() override {}
    void _stdcall UnlockMix_Old() override {}
    void _stdcall MIDIOut_Delayed(TPluginTag Sender, intptr_t Msg) override {}
    void _stdcall MIDIOut(TPluginTag Sender, intptr_t Msg) override {}
    void _stdcall AddWave_32FM_32FS_Ramp(void *SourceBuffer, void *DestBuffer, int Length, float LVol, float RVol, float &LastLVol, float &LastRVol) override {}
    void _stdcall AddWave_32FS_32FS_Ramp(void *SourceBuffer, void *DestBuffer, int Length, float LVol, float RVol, float &LastLVol, float &LastRVol) override {}
    bool _stdcall LoadSample(TSampleHandle &Handle, char *FileName, PWaveFormatExtensible NeededFormat, int Flags) override {return {};}
    void * _stdcall GetSampleData(TSampleHandle Handle, int &Length) override {return nullptr;}
    void _stdcall CloseSample(TSampleHandle Handle) override {}
    int _stdcall GetSongMixingTime() override {return {};}
    double _stdcall GetSongMixingTime_A() override {return {};}
    double _stdcall GetSongPlayingTime() override {return {};}
    void _stdcall OnControllerChanged(TPluginTag Sender, intptr_t Index, intptr_t Value) override {}
    void * _stdcall GetSendBuffer(intptr_t Num) override {return nullptr;}
    void _stdcall PlugMsg_Delayed(TPluginTag Sender, intptr_t Msg) override {}
    void _stdcall PlugMsg_Kill(TPluginTag Sender, intptr_t MSg) override {}
    void _stdcall GetSampleInfo(TSampleHandle Handle, PSampleInfo Info) override {}
    void _stdcall DistWave_32FM(int DistType, int DistThres, void *SourceBuffer, int Length, float DryVol, float WetVol, float Mul) override {}
    void * _stdcall GetMixBuffer(int Num) override {return nullptr;}
    void * _stdcall GetInsBuffer(TPluginTag Sender, int Ofs) override {return nullptr;}
    BOOL _stdcall PromptEdit(int x, int y, char *SetCaption, char *s, int &c) override {return {};}
    void _stdcall SuspendOutput_Old() override {}
    void _stdcall ResumeOutput_Old() override {}
    void _stdcall GetSampleRegion(TSampleHandle Handle, int RegionNum, PSampleRegion Region) override {}
    void _stdcall ComputeLRVol(float &LVol, float &RVol, float Pan, float Volume) override {}
    void _stdcall LockPlugin(TPluginTag Sender) override {}
    void _stdcall UnlockPlugin(TPluginTag Sender) override {}
    void _stdcall LockMix_Shared_Old() override {}
    void _stdcall UnlockMix_Shared_Old() override {}
    void _stdcall GetInBuffer(TPluginTag Sender, intptr_t Index, PIOBuffer IBuffer) override {IBuffer->Buffer=Index>=1&&Index<=routeCount?routes[size_t(Index-1)].data():nullptr;IBuffer->Flags=IBuffer->Buffer?IO_Filled:0;}
    void _stdcall GetOutBuffer(TPluginTag Sender, intptr_t Index, PIOBuffer OBuffer) override {}
    TOutVoiceHandle _stdcall TriggerOutputVoice(TVoiceParams *VoiceParams, intptr_t SetIndex, intptr_t SetTag) override {return {};}
    void _stdcall OutputVoice_Release(TOutVoiceHandle Handle) override {}
    void _stdcall OutputVoice_Kill(TOutVoiceHandle Handle) override {}
    int _stdcall OutputVoice_ProcessEvent(TOutVoiceHandle Handle, intptr_t EventID, intptr_t EventValue, intptr_t Flags) override {return {};}
    BOOL _stdcall PromptEdit_Ex(int x, int y, const char* SetCaption, char* Text, int& Color1, int& Color2, int& IconIndex, int FontHeight, int SetOptions) override {return {};}
    void _stdcall SuspendOutput(TPluginTag Sender) override {}
    void _stdcall ResumeOutput(TPluginTag Sender) override {}
};
std::vector<unsigned char> save(TFruityPlug* p){
    IStream* stream=nullptr;check(SUCCEEDED(CreateStreamOnHGlobal(nullptr,TRUE,&stream)),"allocate native state stream");
    p->SaveRestoreState(stream,TRUE);STATSTG stat{};stream->Stat(&stat,STATFLAG_NONAME);std::vector<unsigned char> bytes(size_t(stat.cbSize.QuadPart));
    LARGE_INTEGER start{};stream->Seek(start,STREAM_SEEK_SET,nullptr);ULONG read=0;stream->Read(bytes.data(),ULONG(bytes.size()),&read);stream->Release();
    check(read==bytes.size()&&bytes.size()>60,"native save adapter writes a full project state");return bytes;
}
void restore(TFruityPlug* p,const std::vector<unsigned char>& bytes){
    IStream* stream=nullptr;check(SUCCEEDED(CreateStreamOnHGlobal(nullptr,TRUE,&stream)),"allocate native restore stream");ULONG written=0;
    stream->Write(bytes.data(),ULONG(bytes.size()),&written);LARGE_INTEGER start{};stream->Seek(start,STREAM_SEEK_SET,nullptr);p->SaveRestoreState(stream,FALSE);stream->Release();
}
int wmain(int argc,wchar_t** argv){try{
    check(argc==2,"native DLL path required");HMODULE library=LoadLibraryW(argv[1]);check(library!=nullptr,"load installed native DLL without external CRT");
    using Create=TFruityPlug* (__stdcall*)(TFruityPlugHost*,int);
    auto create=reinterpret_cast<Create>(GetProcAddress(library,"CreatePlugInstance"));check(create!=nullptr,"native factory export");
    auto host=std::make_unique<Host>();auto plugin=create(host.get(),42);check(plugin!=nullptr,"native plugin creation");
    std::array<float,8192> input{},out{};std::mt19937 rng(73);
    for(int rate:{44100,48000,88200,96000,192000}){plugin->Dispatcher(FPD_SetSampleRate,0,rate);
        for(int length:{16,32,64,127,256,511,1024,2048,4096}){for(int i=0;i<length*2;++i){uint32_t bits=rng();std::memcpy(&input[i],&bits,4);}
            plugin->Eff_Render(reinterpret_cast<PWAV32FS>(input.data()),reinterpret_cast<PWAV32FS>(out.data()),length);
            check(std::memcmp(input.data(),out.data(),length*8)==0,"actual native callback bit-exact passthrough");
            plugin->Eff_Render(reinterpret_cast<PWAV32FS>(input.data()),reinterpret_cast<PWAV32FS>(input.data()),length);check(std::memcmp(input.data(),out.data(),length*8)==0,"native in-place audio remains unchanged");}}
    input.fill(.07f);
    for(int mode:{PM_Normal,PM_HQ_NonRealtime,PM_IsRendering}){plugin->Dispatcher(FPD_ProcessMode,0,mode);plugin->Dispatcher(FPD_Flush,0,0);
        plugin->Eff_Render(reinterpret_cast<PWAV32FS>(input.data()),reinterpret_cast<PWAV32FS>(out.data()),64);check(std::memcmp(input.data(),out.data(),512)==0,"offline/flush transparency");}
    for(int count:{0,1,128,4,64}){host->routeCount=count;plugin->Dispatcher(FPD_RoutingChanged,0,0);
        plugin->Eff_Render(reinterpret_cast<PWAV32FS>(input.data()),reinterpret_cast<PWAV32FS>(out.data()),64);check(std::memcmp(input.data(),out.data(),512)==0,"route churn transparency");}
    HWND parent=CreateWindowW(L"STATIC",L"Native lifecycle test",WS_OVERLAPPEDWINDOW|WS_VISIBLE,0,0,1240,840,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
    check(plugin->Dispatcher(FPD_ShowEditor,0,reinterpret_cast<intptr_t>(parent))==1,"native editor attach");
    HWND editor=plugin->EditorHandle;check(IsWindow(editor),"native editor exposes a valid HWND");
    SendMessageW(editor,WM_LBUTTONDOWN,0,MAKELPARAM(1160,148));SendMessageW(editor,WM_MOUSEMOVE,MK_LBUTTON,MAKELPARAM(1160,310));SendMessageW(editor,WM_LBUTTONUP,0,MAKELPARAM(1160,310));
    auto state=save(plugin);plugin->Dispatcher(FPD_ShowEditor,0,0);check(!IsWindow(editor),"native editor detaches cleanly");
    auto clone=create(host.get(),43);check(clone!=nullptr,"second native instance");restore(clone,state);auto copied=save(clone);
    check(std::memcmp(state.data(),copied.data(),52)==0,"native state adapter persists camera and frequency zoom");
    std::vector<unsigned char> invalid{1,2,3,4,5};restore(clone,invalid);
    clone->Eff_Render(reinterpret_cast<PWAV32FS>(input.data()),reinterpret_cast<PWAV32FS>(out.data()),64);check(std::memcmp(input.data(),out.data(),512)==0,"invalid state cannot affect native audio");
    clone->DestroyObject();
    plugin->Dispatcher(FPD_ShowEditor,0,reinterpret_cast<intptr_t>(parent));editor=plugin->EditorHandle;
    SendMessageW(editor,WM_LBUTTONDOWN,0,MAKELPARAM(1190,32));SendMessageW(editor,WM_LBUTTONUP,0,MAKELPARAM(1190,32));
    plugin->DestroyObject();check(!IsWindow(editor),"destroy while fullscreen closes detached editor");
    DestroyWindow(parent);FreeLibrary(library);
    std::cout<<"PASS: actual native DLL load, 45 sample-rate/block combinations, in-place audio, offline mode, flush, 0-128 route churn, editor reopen, IStream state, corrupted state, multiple instances and fullscreen destruction\n";
    return 0;
}catch(const std::exception& e){std::cerr<<"FAIL: "<<e.what()<<"\n";return 1;}}

