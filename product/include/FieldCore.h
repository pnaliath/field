#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace field {
static_assert(std::atomic<float>::is_always_lock_free && std::atomic<double>::is_always_lock_free &&
              std::atomic<uint64_t>::is_always_lock_free, "Field requires lock-free audio telemetry atomics");
constexpr int Routes = 128, Bands = 76, FFTSize = 4096;
constexpr const char* Version = "1.0.0-beta.1";
inline double nowMs() noexcept {
    return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
inline float db(double v) noexcept { return float(20.0*std::log10(std::max(v,1.e-9))); }
inline float unit(float v) noexcept { return std::clamp(v,0.f,1.f); }
inline float hz(int b) noexcept { return 28.f*std::pow(18000.f/28.f,float(b)/75.f); }
inline float depth(float level) noexcept { return .10f+.72f*unit((-14.f-level)/58.f); }
enum class Kind : uint32_t { Unknown, Source, Bus, Reverb, Delay, Parallel };
inline const char* kindName(Kind k) {
    switch(k) { case Kind::Source:return "Source";case Kind::Bus:return "Bus";
    case Kind::Reverb:return "Reverb";case Kind::Delay:return "Delay";
    case Kind::Parallel:return "Parallel";default:return "Unknown"; }
}
struct RouteView {
    uint64_t id=0;
    char name[96]{};
    uint32_t color=0;
    Kind kind=Kind::Unknown;
    bool visible=true, present=false, ready=false, provisional=false, sustained=false;
    float peak=-180,rms=-180,pan=0,stablePan=0,width=0,z=.5f,presence=0;
    float low=0,high=0,dominant=0,level=-180;
    std::array<float,Bands> shape{},eq{};
    int voices=1;
    std::array<float,2> voicePan{};
    uint32_t onsetCount=0;
    double onsetMs=0,eventMs=0,lastSignalMs=0;
    float eventPan=0,eventZ=.5f,eventWidth=0,eventLife=500;
    std::array<float,Bands> eventShape{};
    int fxSource=-1;
    float reverb=0,delay=0,fxConfidence=0;
};
struct Snapshot {
    std::array<RouteView,Routes> routes{};
    double timeMs=0,analysisMs=0;
    uint64_t dropped=0;
    uint32_t queueDepth=0,active=0;
};
struct Preferences {
    float yaw=.38f,pitch=.20f,zoom=1,animation=1;
    int selected=-1,detail=1,analysis=1;
    bool labels=true,grid=true,fx=true;
};

// One audio producer and one analysis consumer per route. No CAS loops, waits,
// allocation, or host calls. Consumer may skip stale samples without touching
// producer-owned memory. Index wrap is defined unsigned arithmetic.
template<size_t Capacity> struct SampleRing {
    static_assert((Capacity&(Capacity-1))==0);
    struct Sample { float l,r; };
    std::array<Sample,Capacity> data{};
    alignas(64) std::atomic<uint32_t> write{0};
    alignas(64) std::atomic<uint32_t> read{0};
    std::atomic<uint64_t> dropped{0};
    template<class Reader> void push(int n,Reader sample) noexcept {
        auto w=write.load(std::memory_order_relaxed);
        auto r=read.load(std::memory_order_acquire);
        if(n<=0)return;
        if(uint32_t(n)>Capacity-(w-r)){dropped.fetch_add(n,std::memory_order_relaxed);return;}
        for(int i=0;i<n;++i)data[(w+uint32_t(i))&(Capacity-1)]=sample(i);
        write.store(w+uint32_t(n),std::memory_order_release);
    }
    int popLatest(Sample* out,int capacity) noexcept {
        auto r=read.load(std::memory_order_relaxed);
        auto w=write.load(std::memory_order_acquire);
        auto available=w-r;
        if(available>uint32_t(capacity)){r=w-uint32_t(capacity);dropped.fetch_add(available-capacity,std::memory_order_relaxed);}
        int n=int(w-r);
        for(int i=0;i<n;++i)out[i]=data[(r+uint32_t(i))&(Capacity-1)];
        read.store(w,std::memory_order_release);return n;
    }
};

class Engine {
public:
    Engine();
    ~Engine();
    Engine(const Engine&)=delete;
    Engine& operator=(const Engine&)=delete;
    void setRate(double rate) noexcept { if(std::isfinite(rate)&&rate>=8000&&rate<=384000)sampleRate.store(rate); }
    void setRoute(int route,uint64_t id,const std::string& name,Kind kind=Kind::Unknown);
    void removeRoute(int route);
    void setVisible(int route,bool visible);
    void setKind(int route,Kind kind);
    void setColor(int route,uint32_t color);
    void relearn(int route=-1);
    void flush() noexcept { flushRequested.store(true,std::memory_order_release); }
    Snapshot snapshot() const;
    Preferences preferences() const;
    void setPreferences(const Preferences& p);
    std::vector<uint8_t> save() const;
    bool restore(const void* data,size_t size);
    void tickForTest();
    void stop();
    std::atomic<double> callbackMs{0};

    template<class T> void capture(int route,const T* left,const T* right,int n,int stride=1) noexcept {
        if(route<0||route>=Routes||!left||n<=0||stride<1)return;
        auto& r=*audio[route];
        const double sr=sampleRate.load(std::memory_order_relaxed);
        double l2=0,r2=0,mid2=0,side2=0,peak=0;
        auto value=[&](int i) noexcept {
            double l=double(left[size_t(i)*stride]);
            double rr=right?double(right[size_t(i)*stride]):l;
            // Sanitize analysis only. Host audio is copied separately, bit for bit.
            if(!std::isfinite(l))l=0;if(!std::isfinite(rr))rr=0;
            l=std::clamp(l,-1.e6,1.e6);rr=std::clamp(rr,-1.e6,1.e6);
            return typename SampleRing<16384>::Sample{float(l),float(rr)};
        };
        for(int i=0;i<n;++i){auto s=value(i);double l=s.l,rr=s.r;
            l2+=l*l;r2+=rr*rr;mid2+=(l+rr)*(l+rr)*.25;side2+=(l-rr)*(l-rr)*.25;
            peak=std::max(peak,std::max(std::abs(l),std::abs(rr)));}
        float rms=float(std::sqrt((l2+r2)/(2.*n)));
        float pan=float((std::sqrt(r2)-std::sqrt(l2))/(std::sqrt(r2)+std::sqrt(l2)+1.e-18));
        float width=unit(float(std::sqrt(side2)/(std::sqrt(mid2)+std::sqrt(side2)+1.e-18))*1.65f);
        double t=nowMs(),duration=1000.*n/sr;
        r.peak.store(db(peak),std::memory_order_relaxed);r.rms.store(db(rms),std::memory_order_relaxed);
        r.pan.store(pan,std::memory_order_relaxed);r.width.store(width,std::memory_order_relaxed);
        double previousBlock=r.lastBlock.exchange(t,std::memory_order_relaxed);
        if(peak>1.e-6){r.lastSignal.store(t,std::memory_order_relaxed);
            bool resumed=previousBlock==0||t-previousBlock>std::max(80.,duration*2.);
            bool onset=(resumed||rms>std::max(1.e-5f,r.previousRms*1.65f))&&(t-r.lastOnset>=60);
            if(onset){r.lastOnset=t;r.onsetPan.store(pan);r.onsetLevel.store(db(rms));r.onsetTime.store(t);
                r.onsetCount.fetch_add(1,std::memory_order_release);}
        }
        r.previousRms=rms+(r.previousRms-rms)*float(std::exp(-duration/10.));
        // Sample transport is skipped for all-zero blocks; wall-clock decay lives
        // on the worker, so missing host buffers cannot freeze presence.
        if(peak>1.e-8)r.ring.push(n,value);
    }
private:
    struct Audio {
        SampleRing<16384> ring;
        std::atomic<float> peak{-180},rms{-180},pan{0},width{0},onsetPan{0},onsetLevel{-180};
        std::atomic<double> lastBlock{0},lastSignal{0},onsetTime{0};
        std::atomic<uint32_t> onsetCount{0};
        float previousRms=0;double lastOnset=-1000;
    };
    struct Learner {
        std::array<float,FFTSize> l{},r{};
        int count=0,pos=0,frames=0,historyPos=0,historyCount=0;
        std::array<std::array<float,48>,Bands> history{};
        std::array<float,Bands> baseline{},eqCandidate{};
        std::array<float,48> pans{};
        std::array<float,256> envelope{};
        int envelopePos=0,envelopeCount=0;
        int panCount=0,panPos=0;
        double lastAnalysis=0,lastUpdate=0,signalStart=0,eqSince=0,lastOnset=0;
        float level=-180,activeDuration=100,profileDifference=0;
        int changedFrames=0;
        bool restored=false;
    };
    std::array<std::unique_ptr<Audio>,Routes> audio;
    std::array<Learner,Routes> learned{};
    mutable std::mutex mutex;
    Snapshot view;
    Preferences prefs;
    std::array<bool,Routes> reset{};
    std::array<bool,Routes> kindLocked{};
    std::atomic<double> sampleRate{44100};
    std::atomic<bool> running{true},flushRequested{false};
    double lastTick=0;
    int relationshipCursor=0;
    std::thread worker;
    void run() noexcept;
    void tick();
    void analyse(int route,double now);
    void relationships();
};

template<class T> inline void passthrough(const T* input,T* output,int n) noexcept {
    if(!output||n<=0)return;
    if(input&&input!=output)std::memmove(output,input,size_t(n)*sizeof(T));
    else if(!input)std::memset(output,0,size_t(n)*sizeof(T));
}
}
