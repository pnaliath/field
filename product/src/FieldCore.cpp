#include "FieldCore.h"
#include <complex>
#include <limits>

namespace field {
namespace {
void fft(std::array<std::complex<float>,FFTSize>& a) {
    for(int i=1,j=0;i<FFTSize;++i){int bit=FFTSize>>1;for(;j&bit;bit>>=1)j^=bit;j^=bit;if(i<j)std::swap(a[i],a[j]);}
    for(int len=2;len<=FFTSize;len<<=1){auto wlen=std::polar(1.f,-6.28318530718f/len);
        for(int i=0;i<FFTSize;i+=len){std::complex<float> w(1,0);for(int j=0;j<len/2;++j){
            auto u=a[i+j],v=a[i+j+len/2]*w;a[i+j]=u+v;a[i+j+len/2]=u-v;w*=wlen;}}}
}
uint32_t checksum(const uint8_t* p,size_t n){uint32_t c=2166136261u;while(n--)c=(c^*p++)*16777619u;return c;}
struct Writer {
    std::vector<uint8_t> b;
    void u(uint32_t n){for(int i=0;i<4;++i)b.push_back(uint8_t(n>>(8*i)));}
    void f(float n){uint32_t v;std::memcpy(&v,&n,4);u(v);}
};
struct Reader {
    const uint8_t* p;size_t n,pos=0;bool valid=true;
    uint32_t u(){if(pos+4>n){valid=false;return 0;}uint32_t v=0;for(int i=0;i<4;++i)v|=uint32_t(p[pos++])<<(8*i);return v;}
    float f(){auto v=u();float r;std::memcpy(&r,&v,4);if(!std::isfinite(r)){valid=false;return 0;}return r;}
};
void trimShapeEdges(std::array<float,Bands>& shape){
    float peak=*std::max_element(shape.begin(),shape.end());if(peak<=0)return;
    float gate=std::max(.15f,peak*.30f);int lo=0,hi=Bands-1;
    while(lo<Bands&&shape[lo]<gate)++lo;while(hi>=0&&shape[hi]<gate)--hi;
    if(lo<hi){for(int b=0;b<lo;++b)shape[b]=0;for(int b=hi+1;b<Bands;++b)shape[b]=0;}
}
}
Engine::Engine(){for(auto& p:audio)p=std::make_unique<Audio>();worker=std::thread([this]{run();});}
Engine::~Engine(){stop();}
void Engine::stop(){running.store(false);if(worker.joinable())worker.join();}
void Engine::run() noexcept {
    while(running.load(std::memory_order_acquire)){
        try {tick();}catch(...){/* Worker failure cannot propagate to the host. Next tick retries. */}
        std::this_thread::sleep_for(std::chrono::milliseconds(4));
    }
}
void Engine::tickForTest(){tick();}
void Engine::setRoute(int route,uint64_t id,const std::string& name,Kind kind){
    if(route<0||route>=Routes||!id)return;std::lock_guard<std::mutex> lock(mutex);auto& v=view.routes[route];
    if(v.id!=id){
        int previous=-1;for(int i=0;i<Routes;++i)if(i!=route&&view.routes[i].id==id){previous=i;break;}
        if(previous>=0){std::swap(v,view.routes[previous]);std::swap(learned[route],learned[previous]);
            std::swap(reset[route],reset[previous]);std::swap(kindLocked[route],kindLocked[previous]);}
        else{v=RouteView{};v.id=id;reset[route]=true;kindLocked[route]=false;}
        auto& ring=audio[route]->ring;ring.read.store(ring.write.load(std::memory_order_acquire),std::memory_order_release);}
    size_t n=std::min(name.size(),sizeof(v.name)-1);std::memcpy(v.name,name.data(),n);v.name[n]=0;
    if(!kindLocked[route]&&kind!=Kind::Unknown)v.kind=kind;
    v.manualType=kindLocked[route];
}
void Engine::removeRoute(int r){if(r<0||r>=Routes)return;std::lock_guard<std::mutex> lock(mutex);view.routes[r]=RouteView{};reset[r]=true;kindLocked[r]=false;}
void Engine::setVisible(int r,bool v){if(r<0||r>=Routes)return;std::lock_guard<std::mutex> lock(mutex);view.routes[r].visible=v;}
void Engine::setKind(int r,Kind v){if(r<0||r>=Routes)return;std::lock_guard<std::mutex> lock(mutex);view.routes[r].kind=v;kindLocked[r]=v!=Kind::Unknown;view.routes[r].manualType=kindLocked[r];}
void Engine::setColor(int r,uint32_t v){if(r<0||r>=Routes)return;std::lock_guard<std::mutex> lock(mutex);view.routes[r].color=v;}
void Engine::relearn(int route){std::lock_guard<std::mutex> lock(mutex);for(int r=0;r<Routes;++r)if(route<0||route==r){reset[r]=true;
    auto& ring=audio[r]->ring;ring.read.store(ring.write.load(std::memory_order_acquire),std::memory_order_release);}}
Snapshot Engine::snapshot() const {std::lock_guard<std::mutex> lock(mutex);return view;}
Preferences Engine::preferences() const {std::lock_guard<std::mutex> lock(mutex);return prefs;}
void Engine::setPreferences(const Preferences& p){std::lock_guard<std::mutex> lock(mutex);prefs=p;
    prefs.yaw=std::isfinite(p.yaw)?p.yaw:.38f;prefs.pitch=std::clamp(std::isfinite(p.pitch)?p.pitch:.2f,-1.5f,1.5f);
    prefs.zoom=std::clamp(std::isfinite(p.zoom)?p.zoom:1.f,.4f,3.f);prefs.detail=std::clamp(p.detail,0,2);
    prefs.analysis=std::clamp(p.analysis,0,2);prefs.selected=std::clamp(p.selected,-1,Routes-1);
    prefs.animation=std::clamp(std::isfinite(p.animation)?p.animation:1.f,0.f,1.f);prefs.frequency.sanitize();
}
void Engine::tick(){
    double start=nowMs();if(start-lastTick<8)return;lastTick=start;
    std::lock_guard<std::mutex> lock(mutex);
    bool flush=flushRequested.exchange(false);view.active=0;view.queueDepth=0;view.dropped=0;
    const double tickDt=std::clamp(start-view.timeMs,1.,50.);
    std::array<float,Routes> currentLevels{};int currentCount=0;
    for(int i=0;i<Routes;++i)if(view.routes[i].id&&start-audio[i]->lastBlock.load()<100&&audio[i]->rms.load()>-100)
        currentLevels[currentCount++]=.8f*audio[i]->rms.load()+.2f*audio[i]->peak.load();
    float loud=-14.f,span=58.f;
    if(currentCount>1){std::sort(currentLevels.begin(),currentLevels.begin()+currentCount);
        loud=currentLevels[size_t((currentCount-1)*.85f)];span=std::max(24.f,loud-currentLevels[0]);}
    auto levelDepth=[&](float level){return .12f+.66f*unit((loud-level)/span);};
    std::array<SampleRing<16384>::Sample,FFTSize> samples;
    for(int r=0;r<Routes;++r){auto& v=view.routes[r];auto& l=learned[r];auto& a=*audio[r];
        if(reset[r]){l=Learner{};auto id=v.id;auto color=v.color;auto kind=v.kind;auto visible=v.visible;
            char name[96];std::memcpy(name,v.name,96);v=RouteView{};v.id=id;v.color=color;v.kind=kind;v.visible=visible;
            std::memcpy(v.name,name,96);v.manualType=kindLocked[r];reset[r]=false;}
        if(flush){l.count=0;l.pos=0;l.signalStart=0;v.presence=0;v.eventMs=0;v.onsetCount=a.onsetCount.load();
            a.ring.read.store(a.ring.write.load(std::memory_order_acquire),std::memory_order_release);}
        if(!v.id)continue;
        double dt=std::clamp(start-l.lastUpdate,1.,100.);l.lastUpdate=start;
        double lastSignal=a.lastSignal.load();bool signal=start-lastSignal<50&&a.peak.load()>-100;
        v.peak=start-a.lastBlock.load()<100?a.peak.load():-180;v.rms=start-a.lastBlock.load()<100?a.rms.load():-180;
        v.present=signal;v.lastSignalMs=lastSignal;
        l.envelope[l.envelopePos]=signal?std::pow(10.f,v.rms/20.f):0;l.envelopePos=(l.envelopePos+1)%256;
        l.envelopeCount=std::min(256,l.envelopeCount+1);
        if(signal){++view.active;if(!l.signalStart)l.signalStart=start;
            float target=std::max(.15f,unit((v.peak+100)/80));v.presence=std::max(v.presence,target);
            v.pan=a.pan.load();
            if(!l.panAnchored){v.stablePan=v.pan;l.panAnchored=true;}
            else v.stablePan+=(v.pan-v.stablePan)*float(1-std::exp(-dt/4500.));
            v.width+=(a.width.load()-v.width)*float(l.frames<4?1:1-std::exp(-dt/1800.));
            float level=.8f*v.rms+.2f*v.peak;
            if(l.level<-120)l.level=level;else l.level+=(level-l.level)*float(1-std::exp(-dt/650.));
            v.level=l.level;
            if(start-l.signalStart>280 && start-l.lastOnset>220)v.sustained=true;
        }else{v.presence*=float(std::exp(-dt/160.));
            if(l.signalStart){float duration=float(std::max(15.,lastSignal-l.signalStart));
                l.activeDuration=.75f*l.activeDuration+.25f*duration;
                if(duration<220)v.sustained=false;l.signalStart=0;}}
        auto onset=a.onsetCount.load(std::memory_order_acquire);
        if(onset!=v.onsetCount){double born=a.onsetTime.load();double gap=born-l.lastOnset;
            if(gap<220&&l.activeDuration<220)v.sustained=false;
            v.onsetCount=onset;v.onsetMs=born;l.lastOnset=born;
            v.eventMs=born;v.eventPan=a.onsetPan.load();v.eventZ=levelDepth(a.onsetLevel.load());
            if(!v.provisional)v.z=v.eventZ;
            v.eventWidth=v.width;v.eventShape=v.shape;v.eventLife=std::clamp(400.f+l.activeDuration,450.f,900.f);
            l.pans[l.panPos]=v.eventPan;l.panPos=(l.panPos+1)%48;l.panCount=std::min(48,l.panCount+1);
            if(l.panCount>=8&&v.voices==1){float c0=-.5f,c1=.5f;int n0=0,n1=0;
                for(int iteration=0;iteration<8;++iteration){float s0=0,s1=0;n0=n1=0;
                    for(int i=0;i<l.panCount;++i){float p=l.pans[i];if(std::abs(p-c0)<std::abs(p-c1)){s0+=p;++n0;}else{s1+=p;++n1;}}
                    if(n0)c0=s0/n0;if(n1)c1=s1/n1;}
                if(n0>=3&&n1>=3&&n0>=l.panCount*.2&&n1>=l.panCount*.2&&std::abs(c1-c0)>.45f&&v.width<.65f){
                    v.voices=2;v.voicePan={std::min(c0,c1),std::max(c0,c1)};}}}
        int n=a.ring.popLatest(samples.data(),FFTSize);
        for(int i=0;i<n;++i){l.l[l.pos]=samples[i].l;l.r[l.pos]=samples[i].r;l.pos=(l.pos+1)&(FFTSize-1);l.count=std::min(FFTSize,l.count+1);}
        double cadence=prefs.analysis==0?24:prefs.analysis==2?10:16;
        if(n&&l.count>=16&&start-l.lastAnalysis>=cadence){analyse(r,start);l.lastAnalysis=start;}
        view.queueDepth+=a.ring.write.load()-a.ring.read.load();view.dropped+=a.ring.dropped.load();
    }
    for(int r=0;r<Routes;++r){auto& v=view.routes[r];if(!v.id||!v.present||learned[r].level<=-120)continue;
        float target=levelDepth(learned[r].level),step=.00016f*float(tickDt);
        v.z+=std::clamp(target-v.z,-step,step);}
    relationships();
    for(int r=0;r<Routes;++r){auto& v=view.routes[r];auto& l=learned[r];
        if(!kindLocked[r]&&v.kind==Kind::Unknown&&v.ready&&l.envelopeCount>=180&&l.fxCandidateHits<4)v.kind=Kind::Source;}
    view.timeMs=start;view.analysisMs=nowMs()-start;
}
void Engine::analyse(int route,double now){
    auto& l=learned[route];auto& v=view.routes[route];
    std::array<std::complex<float>,FFTSize> left{},right{};
    double sumW=0,ml=0,mr=0;int first=(l.pos-l.count+FFTSize)&(FFTSize-1);
    for(int i=0;i<l.count;++i){int p=(first+i)&(FFTSize-1);ml+=l.l[p];mr+=l.r[p];}ml/=l.count;mr/=l.count;
    for(int i=0;i<l.count;++i){float w=l.count<FFTSize?(.5f-.5f*std::cos(6.28318530718f*(i+.5f)/l.count)):(.5f-.5f*std::cos(6.28318530718f*i/(FFTSize-1)));int p=(first+i)&(FFTSize-1);
        left[i]=float(l.l[p]-ml)*w;right[i]=float(l.r[p]-mr)*w;sumW+=w;}
    fft(left);fft(right);float binHz=float(sampleRate.load()/FFTSize),peak=-180;
    std::array<float,Bands> spectrum{};
    for(int b=0;b<Bands;++b){float lo=hz(b)/1.044f,hi=hz(b)*1.044f;
        int a=std::clamp(int(std::ceil(lo/binHz)),1,FFTSize/2-1),z=std::clamp(int(std::floor(hi/binHz)),a,FFTSize/2-1);
        if(hi<binHz||lo>=sampleRate.load()*.5){spectrum[b]=-180;continue;}
        double energy=0;for(int k=a;k<=z;++k)energy=std::max(energy,double((std::norm(left[k])+std::norm(right[k]))*.5));
        spectrum[b]=db(2*std::sqrt(energy)/std::max(1.,sumW));peak=std::max(peak,spectrum[b]);}
    if(peak<-105)return;
    float cutoff=l.count<FFTSize?28.f:48.f;
    std::array<float,Bands> profile{},shape{};
    for(int b=0;b<Bands;++b){float normalized=spectrum[b]-peak;
        l.history[b][l.historyPos]=normalized;auto values=l.history[b];int count=std::min(48,l.historyCount+1),q=int((count-1)*.82f);
        std::nth_element(values.begin(),values.begin()+q,values.begin()+count);profile[b]=values[q];}
    l.historyPos=(l.historyPos+1)%48;l.historyCount=std::min(48,l.historyCount+1);++l.frames;
    float difference=0;
    for(int b=0;b<Bands;++b){float energy=(std::pow(10.f,profile[std::max(0,b-1)]/10.f)+2*std::pow(10.f,profile[b]/10.f)+std::pow(10.f,profile[std::min(75,b+1)]/10.f))*.25f;
        float smooth=10.f*std::log10(std::max(1.e-18f,energy));float value=unit((smooth+cutoff)/cutoff);if(value<.12f)value=0;
        shape[b]=value;difference+=std::abs(shape[b]-v.shape[b]);}
    for(int b=1;b<Bands-1;++b)if(shape[b]>0&&shape[b-1]==0&&shape[b+1]==0)shape[b]=0;
    for(int b=1;b<Bands-1;++b)if(shape[b]==0&&shape[b-1]>.12f&&shape[b+1]>.12f)shape[b]=(shape[b-1]+shape[b+1])*.5f;
    trimShapeEdges(shape);difference/=Bands;
    if(l.restored){if(difference>.20f)++l.changedFrames;else l.changedFrames=0;
        if(l.changedFrames>12){v.ready=false;l.restored=false;l.historyCount=0;l.frames=1;l.changedFrames=0;}}
    for(int b=0;b<Bands;++b){float alpha=!v.provisional?1.f:l.frames<8?.35f:.018f;v.shape[b]+=(shape[b]-v.shape[b])*alpha;if(l.frames<=8)l.baseline[b]=profile[b];}
    trimShapeEdges(v.shape);v.provisional=true;v.ready=l.frames>=8;
    bool change=false;
    for(int b=1;b<Bands-1;++b){float delta=spectrum[b]-peak-l.baseline[b];float d0=spectrum[b-1]-peak-l.baseline[b-1],d1=spectrum[b+1]-peak-l.baseline[b+1];
        if(v.ready&&std::abs(delta)>5&&delta*d0>0&&delta*d1>0&&v.shape[b]>.15f){l.eqCandidate[b]=std::clamp(delta,-12.f,12.f);change=true;}else l.eqCandidate[b]=0;}
    if(change){if(l.eqSince==0)l.eqSince=now;}else l.eqSince=0;
    for(int b=0;b<Bands;++b){float target=l.eqSince&&now-l.eqSince>900?l.eqCandidate[b]:0;v.eq[b]+=(target-v.eq[b])*.07f;}
    v.low=v.high=v.dominant=0;float maximum=0;
    for(int b=0;b<Bands;++b)if(v.shape[b]>.12f){if(!v.low)v.low=hz(b);v.high=hz(b);if(v.shape[b]>maximum){maximum=v.shape[b];v.dominant=hz(b);}}
    if(v.eventMs&&now-v.eventMs<v.eventLife){bool empty=true;for(float x:v.eventShape)if(x>.12f)empty=false;if(empty)v.eventShape=v.shape;}
}
void Engine::relationships(){
    for(int attempt=0;attempt<4;++attempt){int r=relationshipCursor++%Routes;auto& v=view.routes[r];auto& dst=learned[r];
        if(!v.id||!v.ready||dst.envelopeCount<100)continue;if(v.kind==Kind::Bus||v.kind==Kind::Parallel||v.kind==Kind::Source)continue;
        bool namedFx=v.kind==Kind::Reverb||v.kind==Kind::Delay;
        float best=namedFx?.88f:.965f;float shapeGate=namedFx?.62f:.78f;float lagMargin=.035f;int match=-1,bestLag=0;
        for(int s=0;s<Routes;++s){if(s==r||!view.routes[s].id||!view.routes[s].ready)continue;
            Kind sourceKind=view.routes[s].kind;if(sourceKind==Kind::Reverb||sourceKind==Kind::Delay||sourceKind==Kind::Bus||sourceKind==Kind::Parallel)continue;
            auto& src=learned[s];if(src.envelopeCount<100)continue;
            double dot=0,aa=0,bb=0;for(int b=0;b<Bands;++b){double a=view.routes[s].shape[b],c=v.shape[b];dot+=a*c;aa+=a*a;bb+=c*c;}
            if(dot/std::sqrt(aa*bb+1.e-12)<shapeGate)continue;
            auto corr=[&](int lag){double x=0,y=0,xx=0,yy=0,xy=0;int n=96;
                for(int i=0;i<n;++i){double a=src.envelope[(src.envelopePos-1-i-lag+512)%256],b=dst.envelope[(dst.envelopePos-1-i+512)%256];x+=a;y+=b;xx+=a*a;yy+=b*b;xy+=a*b;}
                double den=std::sqrt(std::max(0.,(xx-x*x/n)*(yy-y*y/n)));return den>1.e-10?float((xy-x*y/n)/den):0.f;};
            float zero=corr(0);for(int lag:{2,4,8,12,16,24,32,48,64}){float c=corr(lag);if(c>best&&c>zero+lagMargin){best=c;match=s;bestLag=lag;}}}
        if(match>=0){int cls=bestLag>=8?2:1;if(dst.fxCandidateSource==match&&dst.fxCandidateClass==cls)dst.fxCandidateHits=std::min(12,dst.fxCandidateHits+1);
            else{dst.fxCandidateSource=match;dst.fxCandidateClass=cls;dst.fxCandidateHits=1;}
            if(dst.fxCandidateHits>=6){v.fxSource=match;v.fxConfidence=best;}
            if(!kindLocked[r]&&v.kind==Kind::Unknown&&dst.fxCandidateHits>=6)v.kind=cls==2?Kind::Delay:Kind::Reverb;}
        else{dst.fxCandidateHits=std::max(0,dst.fxCandidateHits-1);v.fxConfidence*=.94f;if(v.fxConfidence<.8f)v.fxSource=-1;}}
    for(auto& v:view.routes){v.reverb=0;v.delay=0;}
    for(int r=0;r<Routes;++r){const auto& v=view.routes[r];bool namedFx=v.kind==Kind::Reverb||v.kind==Kind::Delay;float confidenceGate=namedFx?.88f:.965f;
        if((v.kind==Kind::Reverb||v.kind==Kind::Delay)&&v.fxSource>=0&&v.fxSource<Routes&&v.fxConfidence>confidenceGate){auto& s=view.routes[v.fxSource];
            float contribution=unit(std::pow(10.f,(v.rms-s.rms)/20.f));float amount=unit(v.presence*v.fxConfidence*contribution);if(v.kind==Kind::Delay)s.delay=std::max(s.delay,amount);else s.reverb=std::max(s.reverb,amount);}}
}
std::vector<uint8_t> Engine::save() const {
    std::lock_guard<std::mutex> lock(mutex);Writer w;w.u(0x31444c46);w.u(3);
    w.f(prefs.yaw);w.f(prefs.pitch);w.f(prefs.zoom);w.f(prefs.animation);w.u(uint32_t(prefs.selected+1));
    w.u(prefs.detail);w.u(prefs.analysis);w.u(prefs.labels|(prefs.grid<<1)|(prefs.fx<<2)|(prefs.sidebarCollapsed<<3)|(prefs.showAllRoutes<<4));
    w.f(prefs.frequency.low);w.f(prefs.frequency.high);
    for(int i=0;i<Routes;++i){const auto& v=view.routes[i];w.u(uint32_t(v.id));w.u(uint32_t(v.id>>32));w.u(v.color);w.u(uint32_t(v.kind));w.u(kindLocked[i]);
        w.u(v.visible);w.u(v.ready);for(char c:v.name)w.b.push_back(uint8_t(c));w.f(v.stablePan);w.f(v.width);w.f(v.z);w.u(v.voices);w.f(v.voicePan[0]);w.f(v.voicePan[1]);for(float s:v.shape)w.f(s);}
    w.u(checksum(w.b.data(),w.b.size()));return w.b;
}
bool Engine::restore(const void* data,size_t size){
    if(!data||size<48||size>128000)return false;Reader r{static_cast<const uint8_t*>(data),size};if(r.u()!=0x31444c46)return false;uint32_t version=r.u();if(version<1||version>3)return false;
    Reader tail{r.p+size-4,4};if(tail.u()!=checksum(r.p,size-4))return false;
    Preferences p;p.yaw=r.f();p.pitch=r.f();p.zoom=r.f();p.animation=r.f();auto selected=r.u();if(selected>Routes)return false;p.selected=int(selected)-1;
    p.detail=int(r.u());p.analysis=int(r.u());auto flags=r.u();p.labels=flags&1;p.grid=flags&2;p.fx=flags&4;
    if(version>=3){p.sidebarCollapsed=flags&8;p.showAllRoutes=flags&16;p.frequency.low=r.f();p.frequency.high=r.f();
        if(p.frequency.low<0||p.frequency.high>1||p.frequency.high-p.frequency.low<MinFrequencySpan-.00001f)return false;}
    if(p.selected<-1||p.selected>=Routes||p.detail<0||p.detail>2||p.analysis<0||p.analysis>2||p.zoom<.4||p.zoom>3||std::abs(p.pitch)>1.5||p.animation<0||p.animation>1)return false;
    auto restored=std::make_unique<Snapshot>();std::array<bool,Routes> restoredLocked{};
    for(int i=0;i<Routes;++i){auto& v=restored->routes[i];v.id=r.u();v.id|=uint64_t(r.u())<<32;v.color=r.u();Kind stored=Kind(r.u());if(uint32_t(stored)>5)return false;
        bool locked=version>=2?r.u()!=0:(stored==Kind::Bus||stored==Kind::Parallel);if(version==1&&!locked&&(stored==Kind::Source||stored==Kind::Reverb||stored==Kind::Delay))stored=Kind::Unknown;
        // Beta.1 conflated name guesses with manual return overrides. Revalidate those guesses.
        if(version<3&&(stored==Kind::Reverb||stored==Kind::Delay))locked=false;
        v.kind=stored;v.manualType=locked;restoredLocked[i]=locked;v.visible=r.u()!=0;v.ready=r.u()!=0;
        if(r.pos+96>size)return false;std::memcpy(v.name,r.p+r.pos,96);v.name[95]=0;r.pos+=96;
        v.stablePan=r.f();v.width=r.f();v.z=r.f();v.voices=int(r.u());v.voicePan[0]=r.f();v.voicePan[1]=r.f();
        if(std::abs(v.stablePan)>1||v.width<0||v.width>1||v.z<0||v.z>1||v.voices<1||v.voices>2||std::abs(v.voicePan[0])>1||std::abs(v.voicePan[1])>1)return false;
        for(float& s:v.shape){s=r.f();if(s<0||s>1)return false;}trimShapeEdges(v.shape);v.provisional=v.ready;}
    if(!r.valid||r.pos+4!=size)return false;
    std::lock_guard<std::mutex> lock(mutex);view=*restored;prefs=p;kindLocked=restoredLocked;
    for(int i=0;i<Routes;++i){learned[i]=Learner{};learned[i].restored=view.routes[i].ready;learned[i].panAnchored=view.routes[i].ready;reset[i]=false;}
    return true;
}
}

