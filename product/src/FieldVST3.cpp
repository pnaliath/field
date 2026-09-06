#include "FieldView.h"
#include "public.sdk/source/vst/vstsinglecomponenteffect.h"
#include "public.sdk/source/common/pluginview.h"
#include "public.sdk/source/main/pluginfactory.h"
#include "pluginterfaces/base/ibstream.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include "pluginterfaces/vst/ivstparameterchanges.h"
#include <commctrl.h>

using namespace Steinberg;
using namespace Steinberg::Vst;
namespace {
const FUID FieldUID(0x8E8253CD,0xA76E435F,0x9F347C31,0x85C98B12);
const FUID SenderUID(0x987FDB41,0xF0B24252,0x8C35D886,0xC8D14870);
HINSTANCE module(){HMODULE h=nullptr;GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCWSTR>(&module),&h);return h;}
std::atomic<uint64_t> sourceSequence{1};
uint64_t newSourceId(){return (uint64_t(field::nowMs())<<20)^sourceSequence.fetch_add(1);}
struct Session {
    field::Engine engine;
    std::array<bool,field::Routes> used{};
    std::array<uint64_t,field::Routes> ownerId{};
    std::mutex mutex;
    std::atomic<int> senders{0},masters{0};
    int claim(){std::lock_guard<std::mutex> lock(mutex);for(int i=1;i<field::Routes;++i)if(!used[i]){used[i]=true;senders.fetch_add(1);return i;}return -1;}
    void identify(int route,uint64_t& id){std::lock_guard<std::mutex> lock(mutex);
        for(int i=1;i<field::Routes;++i)if(i!=route&&used[i]&&ownerId[i]==id){id=newSourceId();break;}ownerId[route]=id;}
    void release(int route){if(route<1)return;std::lock_guard<std::mutex> lock(mutex);if(used[route]){used[route]=false;ownerId[route]=0;senders.fetch_sub(1);engine.removeRoute(route);}}
};
std::mutex registryMutex;
std::array<std::weak_ptr<Session>,16> registry;
std::shared_ptr<Session> session(int n){std::lock_guard<std::mutex> lock(registryMutex);auto s=registry[n].lock();if(!s){s=std::make_shared<Session>();registry[n]=s;}return s;}
int freeSession(){std::lock_guard<std::mutex> lock(registryMutex);for(int i=0;i<16;++i){auto s=registry[i].lock();if(!s||!s->masters.load())return i;}return -1;}
class Plugin;
class Editor:public CPluginView {
    Plugin& plugin;std::unique_ptr<field::View> view;HWND panel=nullptr,combo=nullptr,name=nullptr;
    static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l);
public:
    explicit Editor(Plugin& p);
    ~Editor() override{removed();}
    tresult PLUGIN_API isPlatformTypeSupported(FIDString type) override{return type&&std::strcmp(type,kPlatformTypeHWND)==0?kResultTrue:kResultFalse;}
    tresult PLUGIN_API attached(void* parent,FIDString type) override;
    tresult PLUGIN_API removed() override{view.reset();if(panel){DestroyWindow(panel);panel=nullptr;}return CPluginView::removed();}
    tresult PLUGIN_API onSize(ViewRect* r) override{if(!r)return kInvalidArgument;rect=*r;if(view)view->resize(r->getWidth(),r->getHeight());return kResultOk;}
};
class Plugin:public SingleComponentEffect {
public:
    bool sender;
    std::array<std::shared_ptr<Session>,16> held;
    std::array<int,16> route{};
    std::atomic<int> active{-1};
    std::atomic<bool> bypass{false};
    std::string sourceName="Source";
    uint64_t sourceId=newSourceId();
    explicit Plugin(bool isSender):sender(isSender){route.fill(-1);}
    ~Plugin() override{for(int i=0;i<16;++i)if(held[i]){if(sender)held[i]->release(route[i]);else held[i]->masters.fetch_sub(1);}}
    void connect(int n){
        if(n<0||n>=16){active.store(-1,std::memory_order_release);return;}
        if(!held[n]){held[n]=session(n);if(sender){route[n]=held[n]->claim();if(route[n]<0){held[n].reset();return;}}
            else{held[n]->masters.fetch_add(1);held[n]->engine.setRoute(0,1,"Master",field::Kind::Bus);}}
        if(sender){held[n]->identify(route[n],sourceId);held[n]->engine.setRoute(route[n],sourceId,sourceName,field::Kind::Source);}
        if(processSetup.sampleRate>=8000)held[n]->engine.setRate(processSetup.sampleRate);
        active.store(n,std::memory_order_release);
    }
    static FUnknown* createField(void*){try{return static_cast<IAudioProcessor*>(new Plugin(false));}catch(...){return nullptr;}}
    static FUnknown* createSender(void*){try{return static_cast<IAudioProcessor*>(new Plugin(true));}catch(...){return nullptr;}}
    tresult PLUGIN_API initialize(FUnknown* context) override{auto result=SingleComponentEffect::initialize(context);if(result!=kResultOk)return result;
        addAudioInput(STR16("Input"),SpeakerArr::kStereo);addAudioOutput(STR16("Output"),SpeakerArr::kStereo);
        parameters.addParameter(STR16("Bypass"),nullptr,1,0,ParameterInfo::kIsBypass,0);
        if(!sender){int n=freeSession();if(n>=0)connect(n);}return kResultOk;}
    tresult PLUGIN_API setupProcessing(ProcessSetup& setup) override{auto result=SingleComponentEffect::setupProcessing(setup);
        for(auto& s:held)if(s)s->engine.setRate(setup.sampleRate);return result;}
    tresult PLUGIN_API setProcessing(TBool) override{return kResultOk;}
    ParamValue PLUGIN_API getParamNormalized(ParamID id) override {
        return id==0?(bypass.load(std::memory_order_relaxed)?1.:0.):SingleComponentEffect::getParamNormalized(id);
    }
    tresult PLUGIN_API setParamNormalized(ParamID id,ParamValue value) override {
        if(id==0)bypass.store(value>=.5,std::memory_order_relaxed);
        return SingleComponentEffect::setParamNormalized(id,value);
    }
    tresult PLUGIN_API setBusArrangements(SpeakerArrangement* in,int32 ni,SpeakerArrangement* out,int32 no) override{
        if(ni!=1||no!=1||!in||!out||in[0]!=out[0]||(in[0]!=SpeakerArr::kMono&&in[0]!=SpeakerArr::kStereo))return kResultFalse;
        return SingleComponentEffect::setBusArrangements(in,ni,out,no);}
    tresult PLUGIN_API canProcessSampleSize(int32 s) override{return s==kSample32||s==kSample64?kResultTrue:kResultFalse;}
    template<class T>void audio(ProcessData& d,T** in,T** out,int channels,Session* s,int lane){
        // Capture before copy handles legal cross-channel host aliases correctly.
        if(s&&in&&channels>0&&lane>=0)s->engine.capture(lane,in[0],channels>1?in[1]:in[0],d.numSamples);
        if(out)for(int c=0;c<d.outputs[0].numChannels;++c)field::passthrough(in&&c<channels?in[c]:nullptr,out[c],d.numSamples);
    }
    tresult PLUGIN_API process(ProcessData& d) override{
        if(d.inputParameterChanges){int count=std::min<int32>(d.inputParameterChanges->getParameterCount(),128);
            for(int i=0;i<count;++i){auto* q=d.inputParameterChanges->getParameterData(i);if(!q||q->getParameterId()!=0)continue;
                int32 points=q->getPointCount(),offset=0;ParamValue value=0;
                if(points>0&&q->getPoint(points-1,offset,value)==kResultOk)bypass.store(value>=.5,std::memory_order_relaxed);}}
        if(d.numSamples<0)return kInvalidArgument;int n=active.load(std::memory_order_acquire);Session* s=n>=0?held[n].get():nullptr;
        double start=field::nowMs();int lane=sender?(n>=0?route[n]:-1):0;
        if(bypass.load(std::memory_order_relaxed))lane=-1;
        if(s&&!sender&&s->senders.load()>0)lane=-1;
        int channels=d.numInputs>0?d.inputs[0].numChannels:0;
        if(d.numOutputs>0){if(d.symbolicSampleSize==kSample32)audio(d,d.numInputs>0?d.inputs[0].channelBuffers32:nullptr,d.outputs[0].channelBuffers32,channels,s,lane);
            else if(d.symbolicSampleSize==kSample64)audio(d,d.numInputs>0?d.inputs[0].channelBuffers64:nullptr,d.outputs[0].channelBuffers64,channels,s,lane);
            d.outputs[0].silenceFlags=d.numInputs>0?d.inputs[0].silenceFlags:3;}
        if(s)s->engine.callbackMs.store(field::nowMs()-start,std::memory_order_relaxed);return kResultOk;
    }
    IPlugView* PLUGIN_API createView(FIDString type) override {if(type&&std::strcmp(type,ViewType::kEditor)==0){try{return new Editor(*this);}catch(...){}}return nullptr;}
    tresult PLUGIN_API getState(IBStream* stream) override{
        if(!stream)return kInvalidArgument;try{int n=active.load();std::vector<uint8_t> state;
            if(!sender&&n>=0)state=held[n]->engine.save();uint32_t header[]={0x32565346,uint32_t(n+1),uint32_t(state.size()),uint32_t(sourceName.size()),uint32_t(sourceId),uint32_t(sourceId>>32),uint32_t(bypass.load())};int32 written=0;
            if(stream->write(header,sizeof(header),&written)!=kResultOk||written!=sizeof(header))return kResultFalse;
            if(!state.empty()&&(stream->write(state.data(),int32(state.size()),&written)!=kResultOk||written!=int32(state.size())))return kResultFalse;
            if(!sourceName.empty()&&(stream->write(sourceName.data(),int32(sourceName.size()),&written)!=kResultOk||written!=int32(sourceName.size())))return kResultFalse;
            return kResultOk;
        }catch(...){return kResultFalse;}}
    tresult PLUGIN_API setState(IBStream* stream) override{
        if(!stream)return kInvalidArgument;try{uint32_t h[7]{};int32 read=0;
            if(stream->read(h,sizeof(h),&read)!=kResultOk||read!=sizeof(h)||h[0]!=0x32565346||h[1]>16||h[2]>128000||h[3]>95||h[6]>1)return kResultFalse;
            std::vector<uint8_t> state(h[2]);std::string name(h[3],' ');
            if(h[2]&&(stream->read(state.data(),int32(h[2]),&read)!=kResultOk||read!=int32(h[2])))return kResultFalse;
            if(h[3]&&(stream->read(name.data(),int32(h[3]),&read)!=kResultOk||read!=int32(h[3])))return kResultFalse;
            sourceName=name;sourceId=uint64_t(h[4])|(uint64_t(h[5])<<32);if(!sourceId)return kResultFalse;
            connect(int(h[1])-1);int n=active.load();if(!sender&&n>=0&&!state.empty()&&!held[n]->engine.restore(state.data(),state.size()))return kResultFalse;
            setParamNormalized(0,h[6]?1.:0.);return kResultOk;
        }catch(...){return kResultFalse;}}
    tresult PLUGIN_API setComponentState(IBStream* stream) override {
        if(!stream)return kInvalidArgument;uint32_t h[7]{};int32 read=0;
        if(stream->read(h,sizeof(h),&read)!=kResultOk||read!=sizeof(h)||h[0]!=0x32565346||h[6]>1)return kResultFalse;
        return setParamNormalized(0,h[6]?1.:0.);
    }
};
Editor::Editor(Plugin& p):plugin(p){rect={0,0,p.sender?400:1200,p.sender?200:760};}
tresult Editor::attached(void* parent,FIDString type){
    if(!parent||isPlatformTypeSupported(type)!=kResultTrue)return kResultFalse;
    try{int n=plugin.active.load();if(!plugin.sender&&n>=0){view=std::make_unique<field::View>(plugin.held[n]->engine,module());
        view->mode=L"Link session "+std::to_wstring(n+1);if(!view->attach(static_cast<HWND>(parent)))return kResultFalse;
    }else{WNDCLASSW wc{};wc.hInstance=module();wc.lpfnWndProc=proc;wc.lpszClassName=L"FieldSenderEditor1";wc.hbrBackground=HBRUSH(COLOR_BTNFACE+1);RegisterClassW(&wc);
        panel=CreateWindowW(wc.lpszClassName,L"Field Sender",WS_CHILD|WS_VISIBLE,0,0,400,200,static_cast<HWND>(parent),nullptr,module(),this);
        CreateWindowW(L"STATIC",L"FIELD SENDER  1.0.0-beta.1",WS_CHILD|WS_VISIBLE,20,18,360,24,panel,nullptr,module(),nullptr);
        CreateWindowW(L"STATIC",L"Link to the session number shown in Field:",WS_CHILD|WS_VISIBLE,20,51,360,20,panel,nullptr,module(),nullptr);
        combo=CreateWindowW(L"COMBOBOX",L"",WS_CHILD|WS_VISIBLE|CBS_DROPDOWNLIST|WS_VSCROLL,20,77,360,240,panel,HMENU(100),module(),nullptr);
        SendMessageW(combo,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(L"Disconnected"));
        for(int i=1;i<=16;++i){auto title=L"Link session "+std::to_wstring(i);SendMessageW(combo,CB_ADDSTRING,0,reinterpret_cast<LPARAM>(title.c_str()));}
        SendMessageW(combo,CB_SETCURSEL,n+1,0);
        CreateWindowW(L"STATIC",L"Source name",WS_CHILD|WS_VISIBLE,20,113,110,20,panel,nullptr,module(),nullptr);
        name=CreateWindowA("EDIT",plugin.sourceName.c_str(),WS_CHILD|WS_VISIBLE|WS_BORDER|ES_AUTOHSCROLL,130,110,250,26,panel,HMENU(101),module(),nullptr);
        SendMessageW(name,EM_SETLIMITTEXT,95,0);CreateWindowW(L"STATIC",L"Audio passes through unchanged. Analysis stays local.",WS_CHILD|WS_VISIBLE,20,156,370,24,panel,nullptr,module(),nullptr);
    }}catch(...){return kResultFalse;}return CPluginView::attached(parent,type);
}
LRESULT CALLBACK Editor::proc(HWND h,UINT m,WPARAM w,LPARAM l){auto self=reinterpret_cast<Editor*>(GetWindowLongPtrW(h,GWLP_USERDATA));
    if(m==WM_NCCREATE){self=static_cast<Editor*>(reinterpret_cast<CREATESTRUCTW*>(l)->lpCreateParams);SetWindowLongPtrW(h,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(self));}
    if(self&&m==WM_COMMAND){try{if(LOWORD(w)==100&&HIWORD(w)==CBN_SELCHANGE){int n=int(SendMessageW(self->combo,CB_GETCURSEL,0,0))-1;self->plugin.connect(n);
            }
        if(LOWORD(w)==101&&HIWORD(w)==EN_KILLFOCUS){char name[96]{};GetWindowTextA(self->name,name,96);self->plugin.sourceName=name;
            int n=self->plugin.active.load();if(n>=0)self->plugin.connect(n);}
    }catch(...){}}
    return DefWindowProcW(h,m,w,l);
}
}
bool InitModule(){return true;}
bool DeinitModule(){return true;}
BEGIN_FACTORY_DEF("Field","https://github.com/pnaliath/field","")
DEF_CLASS2(INLINE_UID_FROM_FUID(FieldUID),PClassInfo::kManyInstances,kVstAudioEffectClass,"Field 1.0 Beta",0,"Fx|Analyzer","1.0.0-beta.1",kVstVersionString,Plugin::createField)
DEF_CLASS2(INLINE_UID_FROM_FUID(SenderUID),PClassInfo::kManyInstances,kVstAudioEffectClass,"Field Sender 1.0 Beta",0,"Fx|Analyzer","1.0.0-beta.1",kVstVersionString,Plugin::createSender)
END_FACTORY
