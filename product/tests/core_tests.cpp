#include "FieldCore.h"
#include <cstdlib>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <new>
thread_local bool forbidAlloc=false;
void* operator new(std::size_t n){if(forbidAlloc)throw std::bad_alloc();if(auto p=std::malloc(n))return p;throw std::bad_alloc();}
void operator delete(void* p) noexcept{std::free(p);}
void operator delete(void* p,std::size_t) noexcept{std::free(p);}
void require(bool x,const char* why){if(!x)throw std::runtime_error(why);}
void next(){std::this_thread::sleep_for(std::chrono::milliseconds(16));}
int main(){try{
    auto e=std::make_unique<field::Engine>();e->stop();e->setRoute(0,101,"Bass");e->tickForTest();
    std::array<float,8192> input{},output{};std::array<double,8192> input64{},output64{};
    std::mt19937 random(12);
    const int blocks[]={16,32,64,127,128,256,511,1024,2048,4096};
    for(double sr:{44100.,48000.,88200.,96000.,192000.}){e->setRate(sr);
        for(int n:blocks){for(int i=0;i<n*2;++i){uint32_t bits=random();std::memcpy(&input[i],&bits,4);input64[i]=double(input[i]);}
            input[0]=std::numeric_limits<float>::denorm_min();input[1]=std::numeric_limits<float>::infinity();
            forbidAlloc=true;field::passthrough(input.data(),output.data(),n*2);
            e->capture(0,input.data(),input.data()+1,n,2);field::passthrough(input64.data(),output64.data(),n*2);forbidAlloc=false;
            require(std::memcmp(input.data(),output.data(),size_t(n)*8)==0,"32-bit transparency");
            require(std::memcmp(input64.data(),output64.data(),size_t(n)*16)==0,"64-bit transparency");
            field::passthrough(input.data(),input.data(),n*2);
        }}
    field::passthrough<float>(nullptr,output.data(),8192);for(float v:output)require(v==0,"null input silence");
    e->relearn();next();e->tickForTest();e->setRate(48000);
    e->setRoute(1,102,"Hat");e->setRoute(2,103,"Anti-phase tone");e->setRoute(3,104,"Quiet bass");next();e->tickForTest();
    double phase=0;
    for(int step=0;step<30;++step){std::array<float,1024> bass{},hat{},anti{},neg{},quiet{};
        for(int i=0;i<1024;++i){double t=(phase+i)/48000.;bass[i]=float(.2*std::sin(t*60*6.283185307));hat[i]=float(.2*std::sin(t*9000*6.283185307));
            anti[i]=float(.2*std::sin(t*1000*6.283185307));neg[i]=-anti[i];quiet[i]=bass[i]*.1f;}
        phase+=1024;e->capture(0,bass.data(),bass.data(),1024);e->capture(1,hat.data(),hat.data(),1024);
        e->capture(2,anti.data(),neg.data(),1024);e->capture(3,quiet.data(),quiet.data(),1024);next();e->tickForTest();}
    auto s=e->snapshot();for(int i=0;i<4;++i)std::cout<<i<<" bounds "<<s.routes[i].low<<" "<<s.routes[i].high<<" z "<<s.routes[i].z<<" width "<<s.routes[i].width<<"\n";require(s.routes[0].provisional,"bass visible");require(s.routes[0].high<1500,"bass must not reach high ceiling");
    require(s.routes[1].low>2000,"hat belongs high");require(s.routes[2].provisional&&s.routes[2].width>.8,"anti-phase stereo must remain visible and wide");
    require(s.routes[3].z>s.routes[0].z,"quieter source further back");
    auto p=e->preferences();p.yaw=.8f;p.selected=2;e->setPreferences(p);e->setVisible(1,false);
    auto state=e->save();auto restored=std::make_unique<field::Engine>();restored->stop();
    require(restored->restore(state.data(),state.size()),"state roundtrip");require(!restored->snapshot().routes[1].visible,"hidden state");
    require(restored->preferences().selected==2,"selection persists");state[state.size()/2]^=0x55;
    require(!restored->restore(state.data(),state.size()),"corrupt state rejected");require(!restored->restore(state.data(),8),"truncated state rejected");
    for(int i=0;i<800;++i){std::array<uint8_t,128> garbage;for(auto& c:garbage)c=uint8_t(random());require(!restored->restore(garbage.data(),garbage.size()),"malformed state rejected");}
    field::SampleRing<1024> ring;std::atomic<bool> done{false};
    std::thread producer([&]{for(int n=0;n<20000;++n)ring.push(32,[n](int i){return field::SampleRing<1024>::Sample{float(n*32+i),-float(n*32+i)};});done.store(true);});
    std::array<field::SampleRing<1024>::Sample,128> data;float last=-1;
    while(!done.load()||ring.write.load()!=ring.read.load()){int n=ring.popLatest(data.data(),128);for(int i=0;i<n;++i){require(data[i].l==-data[i].r,"torn stereo ring sample");require(data[i].l>last,"ring sample ordering");last=data[i].l;}}
    producer.join();
    for(int i=4;i<64;++i)e->setRoute(i,100+i,"Stress source");next();e->tickForTest();
    std::array<float,64> block;for(int i=0;i<64;++i)block[i]=float(.1*std::sin(i*.17));
    double start=field::nowMs();for(int frame=0;frame<300;++frame){forbidAlloc=true;for(int i=0;i<64;++i)e->capture(i,block.data(),block.data(),64);forbidAlloc=false;}
    std::cout<<"PASS: bit-exact mono/stereo float32/float64 passthrough; five sample rates; variable 16-4096 buffers; nonfinite analysis; no capture allocation; frequency separation; anti-phase; depth; state roundtrip/corruption; concurrent ring; 64-route bounded overload.\n";
    std::cout<<"64-route capture batch mean ms: "<<(field::nowMs()-start)/300<<" (Linux synthetic measurement, not a DAW guarantee)\n";
    return 0;
}catch(const std::exception& ex){forbidAlloc=false;std::cerr<<"FAIL: "<<ex.what()<<"\n";return 1;}}
