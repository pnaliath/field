#include "FieldView.h"
#include <cmath>
#include <iostream>
int main(){
    auto engine=std::make_unique<field::Engine>();engine->setRate(48000);
    const char* names[]={"Kick","Bass","Vocal","Guitar L","Guitar R","Pad","Hi-hat","Flute"};
    float frequencies[]={60,100,800,420,600,1800,9000,1600};
    for(int i=0;i<8;++i)engine->setRoute(i,i+1,names[i],field::Kind::Source);
    HWND parent=CreateWindowW(L"STATIC",L"Field renderer validation",WS_OVERLAPPEDWINDOW|WS_VISIBLE,0,0,1200,800,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
    field::View view(*engine,GetModuleHandleW(nullptr));view.mode=L"Synthetic renderer test";
    if(!view.attach(parent))return 1;
    auto p=engine->preferences();p.selected=2;engine->setPreferences(p);
    for(int block=0;block<150;++block){for(int r=0;r<8;++r){std::array<float,768> l{},rr{};
            for(int i=0;i<768;++i){double t=(block*768+i)/48000.;float v=float(.18*std::sin(t*frequencies[r]*6.283185307));
                if(r==2)v+=float(.06*std::sin(t*2200*6.283185307));l[i]=v*(r==4?.2f:1.f);rr[i]=v*(r==3?.2f:1.f);}
            engine->capture(r,l.data(),rr.data(),768);}
        MSG msg;while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){TranslateMessage(&msg);DispatchMessageW(&msg);}Sleep(16);}
    RECT rect;GetClientRect(view.window(),&rect);HDC dc=GetDC(view.window());HDC memory=CreateCompatibleDC(dc);
    HBITMAP bitmap=CreateCompatibleBitmap(dc,rect.right,rect.bottom);HGDIOBJ old=SelectObject(memory,bitmap);
    BitBlt(memory,0,0,rect.right,rect.bottom,dc,0,0,SRCCOPY);Gdiplus::Bitmap image(bitmap,nullptr);
    UINT count=0,size=0;Gdiplus::GetImageEncodersSize(&count,&size);std::vector<uint8_t> storage(size);
    auto codecs=reinterpret_cast<Gdiplus::ImageCodecInfo*>(storage.data());Gdiplus::GetImageEncoders(count,size,codecs);
    bool saved=false;for(UINT i=0;i<count;++i)if(wcscmp(codecs[i].MimeType,L"image/png")==0)saved=image.Save(L"Field-render-check.png",&codecs[i].Clsid)==Gdiplus::Ok;
    SelectObject(memory,old);DeleteObject(bitmap);DeleteDC(memory);ReleaseDC(view.window(),dc);
    std::cout<<(saved?"Renderer PNG saved\n":"Renderer capture failed\n");return saved?0:1;
}
