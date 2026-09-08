#include "FieldView.h"
#include <commdlg.h>
#include <windowsx.h>
#include <sstream>
#include <iomanip>
#include <cctype>

namespace field {
using namespace Gdiplus;
namespace {
constexpr int SidebarWidth=238;
constexpr int CollapsedSidebarWidth=30;
constexpr int ListTop=136;
constexpr float RoomHalfX=1.30f;
constexpr float RoomFront=.03f;
constexpr float RoomBack=.97f;
Color color(const RouteView& r,int alpha=255){
    static constexpr uint32_t palette[]={0x46c9bb,0xf3b85f,0x9791fa,0xef879f,0x74b7ed,0xb7d575,0xe99863,0x8bd4da,0xc892d2,0xe5d98c,0x7493e5,0xdd8d73};
    uint32_t c=r.color?r.color:palette[r.id%12];return Color(BYTE(std::clamp(alpha,0,255)),BYTE(c>>16),BYTE(c>>8),BYTE(c));
}
std::wstring wide(const char* s){if(!s||!*s)return L"Unnamed source";int n=MultiByteToWideChar(CP_UTF8,0,s,-1,nullptr,0);
    if(n<=0)return L"Source";std::wstring w(size_t(n),0);MultiByteToWideChar(CP_UTF8,0,s,-1,w.data(),n);w.resize(n-1);return w;}
void text(Graphics& g,const std::wstring& s,float x,float y,float w,float h,Color c,float size=12,bool bold=false){
    Font f(L"Segoe UI",size,bold?FontStyleBold:FontStyleRegular,UnitPixel);SolidBrush b(c);StringFormat fmt;
    fmt.SetTrimming(StringTrimmingEllipsisCharacter);fmt.SetFormatFlags(StringFormatFlagsNoWrap);g.DrawString(s.c_str(),-1,&f,RectF(x,y,w,h),&fmt,&b);}
void button(Graphics& g,const wchar_t* label,float x,float y,float w,float h){SolidBrush fill(Color(255,29,41,49));Pen edge(Color(255,56,74,84));g.FillRectangle(&fill,x,y,w,h);g.DrawRectangle(&edge,x,y,w,h);text(g,label,x+8,y+3,w-16,h-4,Color(255,184,199,204),11,true);}
std::wstring number(float v,int decimals=1){std::wostringstream s;s<<std::fixed<<std::setprecision(decimals)<<v;return s.str();}
bool overlap(const RectF& a,const RectF& b){return a.X<b.GetRight()&&a.GetRight()>b.X&&a.Y<b.GetBottom()&&a.GetBottom()>b.Y;}
bool heard(const RouteView& v){return v.id&&(v.present||v.provisional||v.ready||v.lastSignalMs>0);}
uint32_t hash32(uint32_t x){x^=x>>16;x*=0x7feb352du;x^=x>>15;x*=0x846ca68bu;x^=x>>16;return x;}
float noise01(uint32_t x){return float(hash32(x)&0xffffu)/65535.f;}
}

View::~View(){if(log)fclose(log);backBuffer.reset();if(hwnd)DestroyWindow(hwnd);if(gdiplus)GdiplusShutdown(gdiplus);}
bool View::attach(HWND parent){
    GdiplusStartupInput input;if(GdiplusStartup(&gdiplus,&input,nullptr)!=Ok)return false;
    WNDCLASSEXW wc{};wc.cbSize=sizeof(wc);wc.style=CS_DBLCLKS;wc.lpfnWndProc=proc;wc.hInstance=instance;
    wc.hCursor=LoadCursor(nullptr,IDC_ARROW);wc.lpszClassName=L"FieldProductionView1";RegisterClassExW(&wc);
    prefs=engine.preferences();visibleDelay.fill(-1);hostParent=parent;
    hwnd=CreateWindowExW(0,wc.lpszClassName,L"Field",WS_CHILD|WS_VISIBLE|WS_CLIPSIBLINGS,0,0,1200,760,parent,nullptr,instance,this);
    if(hwnd)SetTimer(hwnd,1,16,nullptr);return hwnd!=nullptr;
}
void View::resize(int w,int h){if(hwnd&&!fullscreen)SetWindowPos(hwnd,nullptr,0,0,w,h,SWP_NOZORDER);}
void View::toggleFullscreen(){
    if(!hwnd)return;
    if(!fullscreen){
        savedParent=GetParent(hwnd);if(!savedParent)savedParent=hostParent;savedStyle=GetWindowLongPtrW(hwnd,GWL_STYLE);
        SetWindowLongPtrW(hwnd,GWL_STYLE,(savedStyle&~WS_CHILD)|WS_POPUP|WS_VISIBLE);SetParent(hwnd,nullptr);
        HMONITOR monitor=MonitorFromWindow(savedParent?savedParent:hwnd,MONITOR_DEFAULTTONEAREST);MONITORINFO mi{};mi.cbSize=sizeof(mi);
        if(GetMonitorInfoW(monitor,&mi)){fullscreen=true;SetWindowPos(hwnd,HWND_TOP,mi.rcMonitor.left,mi.rcMonitor.top,mi.rcMonitor.right-mi.rcMonitor.left,mi.rcMonitor.bottom-mi.rcMonitor.top,SWP_FRAMECHANGED|SWP_SHOWWINDOW);SetFocus(hwnd);}
    }else{
        SetWindowLongPtrW(hwnd,GWL_STYLE,savedStyle);SetParent(hwnd,savedParent?savedParent:hostParent);fullscreen=false;
        RECT r{};HWND parent=savedParent?savedParent:hostParent;if(parent&&GetClientRect(parent,&r))SetWindowPos(hwnd,nullptr,0,0,r.right-r.left,r.bottom-r.top,SWP_NOZORDER|SWP_FRAMECHANGED|SWP_SHOWWINDOW);
    }
    backBuffer.reset();backW=backH=0;InvalidateRect(hwnd,nullptr,FALSE);
}
LRESULT CALLBACK View::proc(HWND h,UINT m,WPARAM w,LPARAM l){auto self=reinterpret_cast<View*>(GetWindowLongPtrW(h,GWLP_USERDATA));
    if(m==WM_NCCREATE){self=static_cast<View*>(reinterpret_cast<CREATESTRUCTW*>(l)->lpCreateParams);SetWindowLongPtrW(h,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(self));self->hwnd=h;}
    if(self){try{return self->message(m,w,l);}catch(...){return DefWindowProcW(h,m,w,l);}}return DefWindowProcW(h,m,w,l);
}
LRESULT View::message(UINT m,WPARAM w,LPARAM l){
    switch(m){
    case WM_TIMER:if(onIdle)onIdle();InvalidateRect(hwnd,nullptr,FALSE);return 0;
    case WM_ERASEBKGND:return 1;
    case WM_PAINT:paint();return 0;
    case WM_LBUTTONDOWN:if(frequencyHit(GET_X_LPARAM(l))&&GET_Y_LPARAM(l)>125){
        RECT c{};GetClientRect(hwnd,&c);int y=GET_Y_LPARAM(l);
        if(y>=c.bottom-78){prefs.frequency=FrequencyRange{};savePrefs();InvalidateRect(hwnd,nullptr,FALSE);return 0;}
        frequencyStart=frequencyAt(y);frequencyBefore=prefs.frequency;float tolerance=9.f/std::max(1L,c.bottom-254);
        if(std::abs(frequencyStart-prefs.frequency.high)<tolerance)frequencyDrag=1;
        else if(std::abs(frequencyStart-prefs.frequency.low)<tolerance)frequencyDrag=2;
        else{frequencyDrag=3;if(frequencyStart<prefs.frequency.low||frequencyStart>prefs.frequency.high){prefs.frequency.move(frequencyStart-(prefs.frequency.low+prefs.frequency.high)*.5f);frequencyBefore=prefs.frequency;}}
        engine.setPreferences(prefs);SetCapture(hwnd);InvalidateRect(hwnd,nullptr,FALSE);return 0;}last={GET_X_LPARAM(l),GET_Y_LPARAM(l)};moved=false;dragging=last.x>sidebarWidth()&&last.y>68;if(dragging)SetCapture(hwnd);return 0;
    case WM_MOUSEMOVE:if(frequencyDrag){dragFrequency(GET_Y_LPARAM(l));return 0;}if(dragging){int x=GET_X_LPARAM(l),y=GET_Y_LPARAM(l);if(std::abs(x-last.x)+std::abs(y-last.y)>2)moved=true;
        prefs.yaw-=(x-last.x)*.007f;prefs.pitch=std::clamp(prefs.pitch-(y-last.y)*.006f,-1.5f,1.5f);last={x,y};engine.setPreferences(prefs);InvalidateRect(hwnd,nullptr,FALSE);}return 0;
    case WM_LBUTTONUP:if(frequencyDrag){dragFrequency(GET_Y_LPARAM(l));frequencyDrag=0;ReleaseCapture();savePrefs();return 0;}if(dragging){dragging=false;ReleaseCapture();savePrefs();}if(!moved)click(GET_X_LPARAM(l),GET_Y_LPARAM(l));return 0;
    case WM_LBUTTONDBLCLK:if(frequencyHit(GET_X_LPARAM(l))){prefs.frequency=FrequencyRange{};savePrefs();InvalidateRect(hwnd,nullptr,FALSE);return 0;}if(GET_X_LPARAM(l)>sidebarWidth()){prefs.yaw=.38f;prefs.pitch=.2f;prefs.zoom=1;savePrefs();}return 0;
    case WM_MOUSEWHEEL:{POINT p{GET_X_LPARAM(l),GET_Y_LPARAM(l)};ScreenToClient(hwnd,&p);int steps=GET_WHEEL_DELTA_WPARAM(w)/WHEEL_DELTA;
        if(frequencyHit(p.x)){prefs.frequency.zoom(std::pow(1.18f,float(-steps)),frequencyAt(p.y));savePrefs();}
        else if(!prefs.sidebarCollapsed&&p.x<SidebarWidth)scroll=std::clamp(scroll-steps*3,0,std::max(0,int(rows.size())-8));
        else{prefs.zoom=std::clamp(prefs.zoom*std::pow(1.1f,float(steps)),.4f,3.f);savePrefs();}InvalidateRect(hwnd,nullptr,FALSE);return 0;}
    case WM_RBUTTONUP:if(!prefs.sidebarCollapsed&&GET_X_LPARAM(l)<SidebarWidth)menu(4,GET_X_LPARAM(l),GET_Y_LPARAM(l));return 0;
    case WM_KEYDOWN:if(w==VK_ESCAPE&&fullscreen){toggleFullscreen();return 0;}if(w=='F'&&prefs.selected>=0){prefs.yaw=0;prefs.pitch=0;prefs.zoom=1.3f;savePrefs();}return 0;
    case WM_CAPTURECHANGED:frequencyDrag=0;dragging=false;return 0;
    case WM_DESTROY:KillTimer(hwnd,1);hwnd=nullptr;return 0;
    default:return DefWindowProcW(hwnd,m,w,l);}
}
void View::click(int x,int y){
    RECT client{};GetClientRect(hwnd,&client);
    if((!prefs.sidebarCollapsed&&x>=206&&x<SidebarWidth&&y>=74&&y<=102)||(prefs.sidebarCollapsed&&x>=3&&x<=27&&y>=74&&y<=104)){prefs.sidebarCollapsed=!prefs.sidebarCollapsed;savePrefs();InvalidateRect(hwnd,nullptr,FALSE);return;}
    if(y<62&&x>=client.right-112){toggleFullscreen();return;}
    if(prefs.selected>=0&&prefs.selected<Routes&&frame.routes[prefs.selected].id){float px=float(client.right-365),py=float(client.bottom-255);if(x>=px+238&&x<=px+260&&y>=py+8&&y<=py+30){prefs.selected=-1;savePrefs();InvalidateRect(hwnd,nullptr,FALSE);return;}}
    if(!prefs.sidebarCollapsed&&x>=18&&x<192&&y>=74&&y<101){prefs.showAllRoutes=!prefs.showAllRoutes;savePrefs();return;}
    if(y<66){if(x>=250&&x<335)menu(0,x,60);else if(x<430&&x>=335)menu(1,x,60);else if(x<535&&x>=430)menu(2,x,60);else if(x>=535&&x<645)menu(3,x,60);return;}
    if(!prefs.sidebarCollapsed&&x<SidebarWidth&&y>=102&&y<126){bool show=x<118;for(int r=0;r<Routes;++r)if(frame.routes[r].id)engine.setVisible(r,show);if(onChange)onChange();InvalidateRect(hwnd,nullptr,FALSE);return;}
    if(!prefs.sidebarCollapsed&&x<SidebarWidth&&y>=ListTop){int row=(y-ListTop)/34+scroll;if(row>=0&&row<int(rows.size())){int r=rows[row];
        if(x<42)engine.setVisible(r,!frame.routes[r].visible);else{prefs.selected=r;savePrefs();}if(onChange)onChange();}return;}
}
void View::menu(int which,int x,int y){
    HMENU h=CreatePopupMenu();auto add=[&](UINT id,const wchar_t* label,bool check=false){AppendMenuW(h,MF_STRING|(check?MF_CHECKED:0),id,label);};
    if(which==0){add(1,L"Perspective");add(2,L"Front / frequency + stereo");add(3,L"Top / stereo + depth");add(4,L"Side / frequency + depth");}
    if(which==1){add(5,L"Reset view");add(6,L"Reset visual preferences");}
    if(which==2){add(7,L"Relearn selected source");add(8,L"Relearn all sources");}
    if(which==3){add(10,L"Labels",prefs.labels);add(11,L"Room grid",prefs.grid);add(12,L"Effects",prefs.fx);
        add(13,L"Detail: Low",prefs.detail==0);add(14,L"Detail: Medium",prefs.detail==1);add(15,L"Detail: High",prefs.detail==2);
        add(16,L"Analysis: Fast",prefs.analysis==0);add(17,L"Analysis: Balanced",prefs.analysis==1);add(18,L"Analysis: Precise",prefs.analysis==2);
        add(19,L"Developer diagnostics",diagnostics);add(20,log?L"Stop CSV recording":L"Record diagnostics CSV");}
    if(which==4){int row=(y-ListTop)/34+scroll;if(row<0||row>=int(rows.size())){DestroyMenu(h);return;}prefs.selected=rows[row];
        for(int k=0;k<=5;++k)add(UINT(30+k),wide(kindName(Kind(k))).c_str(),frame.routes[prefs.selected].kind==Kind(k));add(40,L"Source colour...");}
    POINT p{x,y};ClientToScreen(hwnd,&p);UINT id=TrackPopupMenu(h,TPM_RETURNCMD|TPM_NONOTIFY,p.x,p.y,0,hwnd,nullptr);DestroyMenu(h);
    switch(id){case 1:case 5:prefs.yaw=.38f;prefs.pitch=.2f;prefs.zoom=1;break;
    case 2:prefs.yaw=0;prefs.pitch=0;prefs.zoom=1;break;case 3:prefs.yaw=0;prefs.pitch=1.45f;prefs.zoom=1;break;
    case 4:prefs.yaw=1.45f;prefs.pitch=0;prefs.zoom=1;break;
    case 6:prefs=Preferences{};break;case 7:if(prefs.selected>=0)engine.relearn(prefs.selected);break;case 8:engine.relearn();break;
    case 10:prefs.labels=!prefs.labels;break;case 11:prefs.grid=!prefs.grid;break;case 12:prefs.fx=!prefs.fx;break;
    case 13:case 14:case 15:prefs.detail=int(id)-13;break;case 16:case 17:case 18:prefs.analysis=int(id)-16;break;
    case 19:diagnostics=!diagnostics;break;case 20:exportLog();break;
    case 40:if(prefs.selected>=0){CHOOSECOLORW cc{};COLORREF custom[16]{};cc.lStructSize=sizeof(cc);cc.hwndOwner=hwnd;cc.lpCustColors=custom;cc.Flags=CC_FULLOPEN|CC_RGBINIT;
        if(ChooseColorW(&cc))engine.setColor(prefs.selected,(GetRValue(cc.rgbResult)<<16)|(GetGValue(cc.rgbResult)<<8)|GetBValue(cc.rgbResult));}break;
    default:if(id>=30&&id<=35&&prefs.selected>=0)engine.setKind(prefs.selected,Kind(id-30));break;}
    if(id)savePrefs();InvalidateRect(hwnd,nullptr,FALSE);
}
bool View::frequencyHit(int x) const {RECT c{};GetClientRect(hwnd,&c);return x>=c.right-82;}
float View::frequencyAt(int y) const {RECT c{};GetClientRect(hwnd,&c);return unit(1.f-float(y-148)/std::max(1.f,float(c.bottom-254)));}
void View::dragFrequency(int y){
    float value=frequencyAt(y);prefs.frequency=frequencyBefore;
    if(frequencyDrag==1)prefs.frequency.high=std::clamp(value,prefs.frequency.low+MinFrequencySpan,1.f);
    else if(frequencyDrag==2)prefs.frequency.low=std::clamp(value,0.f,prefs.frequency.high-MinFrequencySpan);
    else prefs.frequency.move(value-frequencyStart);
    engine.setPreferences(prefs);InvalidateRect(hwnd,nullptr,FALSE);
}
void View::frequencyBar(Graphics& g,const RECT& c){
    float x=float(c.right-40),top=148.f,bottom=float(c.bottom-106),height=std::max(1.f,bottom-top);
    SolidBrush panel(Color(255,17,25,31));g.FillRectangle(&panel,float(c.right-83),67.f,83.f,float(c.bottom-67));
    text(g,L"FREQ",float(c.right-75),83,68,21,Color(255,173,196,205),11,true);
    text(g,L"ZOOM",float(c.right-75),103,68,20,Color(255,99,131,144),9);
    Pen rail(Color(255,62,88,100),3.f);g.DrawLine(&rail,x,top,x,bottom);
    for(float f:{28.f,120.f,1000.f,8000.f,18000.f}){float axis=std::log(f/28.f)/std::log(18000.f/28.f),y=top+(1-axis)*height;
        Pen tick(Color(255,65,91,103));g.DrawLine(&tick,x-6,y,x+6,y);
        text(g,f>=1000?number(f/1000,0)+L"k":number(f,0),x-37,y-7,29,16,Color(255,96,131,146),9);}
    float high=top+(1-prefs.frequency.high)*height,low=top+(1-prefs.frequency.low)*height;
    SolidBrush selected(Color(170,50,143,143));g.FillRectangle(&selected,x-7,high,14.f,std::max(2.f,low-high));
    SolidBrush handle(Color(255,100,212,196));g.FillRectangle(&handle,x-13,high-4,26.f,8.f);g.FillRectangle(&handle,x-13,low-4,26.f,8.f);
    text(g,number(axisHz(prefs.frequency.high),0),float(c.right-78),top-25,75,20,Color(255,167,219,211),11);
    text(g,number(axisHz(prefs.frequency.low),0),float(c.right-78),bottom+8,75,20,Color(255,167,219,211),11);
    button(g,L"Reset",float(c.right-75),float(c.bottom-74),66,24);
}

PointF View::project(float x,float y,float z,const RECT& room) const {
    float wz=(z-.5f)*1.85f,wy=(prefs.frequency.project(y)-.5f)*1.72f;
    float xx=x*std::cos(prefs.yaw)+wz*std::sin(prefs.yaw),zz=-x*std::sin(prefs.yaw)+wz*std::cos(prefs.yaw);
    float yy=wy*std::cos(prefs.pitch)-zz*std::sin(prefs.pitch),depth=wy*std::sin(prefs.pitch)+zz*std::cos(prefs.pitch);
    float scale=std::min(float(room.right-room.left)*.34f,float(room.bottom-room.top)*.43f)*prefs.zoom/(1.48f+.2f*depth);
    return PointF((room.left+room.right)*.5f+xx*scale,(room.top+room.bottom)*.5f-yy*scale);
}

void View::body(Graphics& g,const RouteView& v,int index,const RECT& room,float pan,float z,float width,float presence,const std::array<float,Bands>& inputShape,int voices){
    auto shape=inputShape;for(int b=0;b<Bands;++b)if(float(b)/75<prefs.frequency.low||float(b)/75>prefs.frequency.high)shape[b]=0;
    if(presence<=.01f)return;
    float crestDb=(v.peak>-150&&v.rms>-150)?std::clamp(v.peak-v.rms,0.f,30.f):0.f;
    if(!v.sustained&&v.eventMs>0)crestDb=std::max(crestDb,10.f);
    float dynamic01=unit((crestDb-2.f)/16.f);
    float depthHalf=.025f+.105f*dynamic01;
    float low=0,high=0,dominant=0,maxShape=0;int stride=prefs.detail==0?9:prefs.detail==2?4:7;
    if(frame.active>8&&index!=prefs.selected)stride=std::max(stride,9);bool drawn=false;
    int firstActive=Bands,lastActive=-1;
    for(int b=0;b<Bands;++b)if(shape[b]>.12f){firstActive=std::min(firstActive,b);lastActive=b;}

    auto radiusX=[&](int b){
        return spectralRadius(shape[b],width,voices)*(1+v.eq[b]*.010f);
    };
    auto radiusZ=[&](int b){
        float gain=std::pow(unit(shape[b]),.42f);
        float rz=depthHalf*(.48f+.52f*gain);
        return std::min(rz,std::max(.012f,std::min(z-.055f,.945f-z)));
    };

    for(int first=0;first<Bands;){
        while(first<Bands&&shape[first]<=.12f)++first;if(first>=Bands)break;
        int end=first;while(end+1<Bands&&shape[end+1]>.12f)++end;if(end==first){first=end+1;continue;}
        for(int b=first;b<=end;++b){if(!low)low=hz(b);high=hz(b);if(shape[b]>maxShape){maxShape=shape[b];dominant=hz(b);}}

        std::vector<PointF> front,back;front.reserve(size_t(end-first+1)*2);back.reserve(size_t(end-first+1)*2);
        for(int b=first;b<=end;++b){float y=float(b)/75,rx=radiusX(b),rz=radiusZ(b);front.push_back(project(pan-rx,y,z-rz,room));back.push_back(project(pan-rx,y,z+rz,room));}
        for(int b=end;b>=first;--b){float y=float(b)/75,rx=radiusX(b),rz=radiusZ(b);front.push_back(project(pan+rx,y,z-rz,room));back.push_back(project(pan+rx,y,z+rz,room));}

        SolidBrush rearFill(color(v,int(presence*11)));SolidBrush frontFill(color(v,int(presence*25)));
        Pen rearEdge(color(v,int(presence*70)),.7f);Pen frontEdge(color(v,int(presence*(index==prefs.selected?235:155))),index==prefs.selected?1.6f:1.f);
        g.FillPolygon(&rearFill,back.data(),int(back.size()));g.DrawPolygon(&rearEdge,back.data(),int(back.size()));

        Pen depthEdge(color(v,int(presence*72)),.7f);
        for(int b=first;b<=end;b+=stride){float y=float(b)/75,rx=radiusX(b),rz=radiusZ(b);
            auto lf=project(pan-rx,y,z-rz,room),lb=project(pan-rx,y,z+rz,room),rf=project(pan+rx,y,z-rz,room),rb=project(pan+rx,y,z+rz,room);
            g.DrawLine(&depthEdge,lf,lb);g.DrawLine(&depthEdge,rf,rb);
        }

        g.FillPolygon(&frontFill,front.data(),int(front.size()));g.DrawPolygon(&frontEdge,front.data(),int(front.size()));

        int pointsN=(index==prefs.selected&&prefs.detail==2)?19:13;
        for(int b=first;b<=end;b+=stride){std::array<PointF,19> points;float rx=radiusX(b),rz=radiusZ(b),y=float(b)/75;
            for(int k=0;k<pointsN;++k){float angle=k*6.2831853f/(pointsN-1);points[k]=project(pan+rx*std::cos(angle),y,z+rz*std::sin(angle),room);}
            Pen ring(color(v,int(presence*105)),.8f);g.DrawLines(&ring,points.data(),pointsN);
        }
        drawn=true;first=end+1;
    }

    if(!drawn)return;auto& metric=rendered[index];metric={true,pan,width,z,low,high,dominant,presence,-1};
    if(v.onsetMs>0&&visibleOnset[index]!=v.onsetCount){visibleOnset[index]=v.onsetCount;visibleDelay[index]=std::max(0.,nowMs()-v.onsetMs);}metric.delay=visibleDelay[index];
    if((prefs.labels||index==prefs.selected)&&low>0){float y=std::log(std::max(28.f,high)/28.f)/std::log(18000.f/28.f);auto p=project(pan,y,z,room);RectF label(p.X-58,p.Y-23,145,21);bool collision=false;
        for(const auto& r:labelRects)if(overlap(label,r))collision=true;if(index==prefs.selected||(!collision&&labelRects.size()<12)){SolidBrush bg(Color(215,18,25,31));g.FillRectangle(&bg,label);text(g,wide(v.name),label.X+5,label.Y+2,label.Width-10,20,color(v),12,index==prefs.selected);labelRects.push_back(label);}}
}

void View::paint(){
    double start=nowMs();frame=engine.snapshot();prefs=engine.preferences();for(auto& r:rendered)r=Rendered{};labelRects.clear();
    PAINTSTRUCT ps{};HDC dc=BeginPaint(hwnd,&ps);RECT client;GetClientRect(hwnd,&client);if(client.right<=0||client.bottom<=0){EndPaint(hwnd,&ps);return;}
    if(!backBuffer||backW!=client.right||backH!=client.bottom){backW=client.right;backH=client.bottom;backBuffer=std::make_unique<Bitmap>(backW,backH,PixelFormat32bppPARGB);}
    Graphics g(backBuffer.get());g.SetSmoothingMode(SmoothingModeAntiAlias);g.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);
    g.Clear(Color(255,13,19,24));
    Pen separator(Color(255,40,53,62));g.DrawLine(&separator,0,66,client.right,66);
    if(!prefs.sidebarCollapsed){
        SolidBrush side(Color(255,19,27,33));g.FillRectangle(&side,0,0,SidebarWidth,client.bottom);g.DrawLine(&separator,SidebarWidth,0,SidebarWidth,client.bottom);
        text(g,L"FIELD",24,17,130,30,Color(255,226,235,238),24,true);text(g,wide(Version),114,26,120,20,Color(255,122,143,153),11);
        text(g,prefs.showAllRoutes?L"ALL ROUTES ▾":L"SOURCES ▾",22,80,150,22,Color(255,112,133,144),11,true);button(g,L"‹",207,74,24,28);
    }else{
        SolidBrush rail(Color(255,19,27,33));g.FillRectangle(&rail,0,0,CollapsedSidebarWidth,client.bottom);g.DrawLine(&separator,CollapsedSidebarWidth,0,CollapsedSidebarWidth,client.bottom);button(g,L"›",3,75,24,28);
        text(g,L"FIELD",48,17,130,30,Color(255,226,235,238),24,true);text(g,wide(Version),138,26,120,20,Color(255,122,143,153),11);
    }
    text(g,L"View",265,25,65,25,Color(255,184,199,204),13);text(g,L"Reset",350,25,70,25,Color(255,184,199,204),13);text(g,L"Learn",445,25,70,25,Color(255,184,199,204),13);text(g,L"Settings",550,25,85,25,Color(255,184,199,204),13);
    float fsX=float(client.right-106);button(g,fullscreen?L"Restore":L"Full screen",fsX,19,92,28);text(g,mode+L"  /  Local analysis",std::max(655.f,fsX-270),26,252,20,Color(255,104,151,144),12);
    rows.clear();for(int r=0;r<Routes;++r){const auto& v=frame.routes[r];if(v.id&&(prefs.showAllRoutes||(heard(v)&&!associatedReturn(v,frame))))rows.push_back(r);}
    if(!prefs.sidebarCollapsed){
        text(g,std::to_wstring(rows.size()),195,80,30,22,Color(255,112,133,144),11);button(g,L"Show All",18,102,92,23);button(g,L"Hide All",118,102,102,23);
        int maxRows=std::max(0,(int(client.bottom)-ListTop-48)/34);scroll=std::clamp(scroll,0,std::max(0,int(rows.size())-maxRows));
        for(int row=scroll;row<int(rows.size())&&row<scroll+maxRows;++row){int r=rows[row];const auto& v=frame.routes[r];float y=float(ListTop)+(row-scroll)*34;
            if(r==prefs.selected){SolidBrush selected(Color(255,32,46,53));g.FillRectangle(&selected,8.f,y-2,222.f,33.f);}Pen box(v.visible?color(v):Color(255,69,83,91));g.DrawRectangle(&box,22.f,y+7,11.f,11.f);
            if(v.visible){SolidBrush dot(color(v));g.FillRectangle(&dot,25.f,y+10,5.f,5.f);}text(g,wide(v.name),44,y,155,20,v.visible?Color(255,205,216,220):Color(255,98,116,126),12,r==prefs.selected);
            text(g,wide(kindName(v.kind)),44,y+17,120,16,Color(255,103,126,136),10);SolidBrush activity(v.present?color(v):Color(255,41,55,63));g.FillEllipse(&activity,213.f,y+10,5.f,5.f);}
        text(g,L"Click to inspect. Right-click for type.",18,float(client.bottom-32),210,20,Color(255,91,112,122),10);
    }
    RECT room{prefs.sidebarCollapsed?38:246,82,client.right-88,client.bottom-40};
    if(prefs.grid){
        Pen boundary(Color(255,49,66,76),1.f),grid(Color(255,39,53,64),.8f);float frequencies[]={28,60,120,250,500,1000,2000,4000,8000,18000};
        for(float yy:{prefs.frequency.low,prefs.frequency.high}){g.DrawLine(&boundary,project(-RoomHalfX,yy,RoomFront,room),project(RoomHalfX,yy,RoomFront,room));g.DrawLine(&boundary,project(-RoomHalfX,yy,RoomBack,room),project(RoomHalfX,yy,RoomBack,room));}
        for(float xx:{-RoomHalfX,RoomHalfX}){g.DrawLine(&boundary,project(xx,prefs.frequency.low,RoomFront,room),project(xx,prefs.frequency.high,RoomFront,room));g.DrawLine(&boundary,project(xx,prefs.frequency.low,RoomBack,room),project(xx,prefs.frequency.high,RoomBack,room));g.DrawLine(&boundary,project(xx,prefs.frequency.low,RoomFront,room),project(xx,prefs.frequency.low,RoomBack,room));g.DrawLine(&boundary,project(xx,prefs.frequency.high,RoomFront,room),project(xx,prefs.frequency.high,RoomBack,room));}
        for(float f:frequencies){float y=std::log(f/28)/std::log(18000.f/28);if(y<prefs.frequency.low||y>prefs.frequency.high)continue;auto a=project(-RoomHalfX,y,RoomBack,room),b=project(RoomHalfX,y,RoomBack,room);g.DrawLine(&grid,a,b);text(g,f>=1000?number(f/1000,0)+L" kHz":number(f,0)+L" Hz",a.X-53,a.Y-8,50,18,Color(255,81,108,125),10);}
        for(float xx:{-1.f,0.f,1.f}){g.DrawLine(&grid,project(xx,prefs.frequency.low,RoomFront,room),project(xx,prefs.frequency.low,RoomBack,room));auto p=project(xx,prefs.frequency.low,RoomFront,room);text(g,xx<0?L"L":xx>0?L"R":L"C",p.X-8,p.Y+9,20,20,Color(255,116,141,151),12);}
        for(float zz:{RoomFront,.5f,RoomBack}){g.DrawLine(&grid,project(-RoomHalfX,prefs.frequency.low,zz,room),project(RoomHalfX,prefs.frequency.low,zz,room));auto p=project(RoomHalfX,prefs.frequency.low,zz,room);text(g,zz<.2?L"Front":zz>.8?L"Back":L"Mid",p.X+9,p.Y-4,45,18,Color(255,92,117,130),10);}
    }
    std::vector<int> order;for(int i=0;i<Routes;++i)if(frame.routes[i].id&&frame.routes[i].visible&&frame.routes[i].provisional&&!associatedReturn(frame.routes[i],frame))order.push_back(i);std::sort(order.begin(),order.end(),[&](int a,int b){return frame.routes[a].z>frame.routes[b].z;});
    if(prefs.selected>=0){auto it=std::find(order.begin(),order.end(),prefs.selected);if(it!=order.end()){order.erase(it);order.insert(order.begin(),prefs.selected);}}
    g.SetClip(Rect(int(room.left),int(room.top-12),int(room.right-room.left),int(room.bottom-room.top+32)));
    for(int i:order){const auto& v=frame.routes[i];if(v.sustained){if(v.voices==2){body(g,v,i,room,std::clamp(v.voicePan[0]+v.pan-(v.voicePan[0]+v.voicePan[1])*.5f,-1.f,1.f),v.z,v.width,v.presence,v.shape,2);body(g,v,i,room,std::clamp(v.voicePan[1]+v.pan-(v.voicePan[0]+v.voicePan[1])*.5f,-1.f,1.f),v.z,v.width,v.presence,v.shape,2);}else body(g,v,i,room,v.pan,v.z,v.width,v.presence,v.shape,1);}
        else{float age=float(start-v.eventMs),life=v.eventLife;float p=v.eventMs>0?unit(1-std::max(0.f,age-80)/std::max(1.f,life-80)):0;if(p>0){bool hasEvent=false;for(float s:v.eventShape)if(s>.12f){hasEvent=true;break;}body(g,v,i,room,v.eventPan,v.eventZ,v.eventWidth,p,hasEvent?v.eventShape:v.shape,v.voices);}else if(v.present)body(g,v,i,room,v.pan,v.z,v.width,v.presence,v.shape,v.voices);}}

    if(prefs.fx){
        for(int fxIndex=0;fxIndex<Routes;++fxIndex){const auto& fx=frame.routes[fxIndex];bool isRev=fx.kind==Kind::Reverb,isDelay=fx.kind==Kind::Delay;
            if(!fx.id||!fx.provisional||(!isRev&&!isDelay))continue;
            if(!fx.visible||fx.fxConfidence<.965f||fx.fxSource<0||fx.fxSource>=Routes)continue;
            int anchor=fx.fxSource;const auto& a=frame.routes[anchor];
            if(!a.id||!a.visible||a.kind==Kind::Reverb||a.kind==Kind::Delay)continue;
            float activity=isRev?a.reverb:a.delay;if(activity<.035f)continue;
            const auto& sh=a.shape;int lo=Bands,hi=-1;
            for(int b=0;b<Bands;++b)if(sh[b]>.12f&&float(b)/75>=prefs.frequency.low&&float(b)/75<=prefs.frequency.high){lo=std::min(lo,b);hi=b;}if(lo>hi)continue;
            float pan=rendered[anchor].drawn?rendered[anchor].pan:a.pan,z=rendered[anchor].drawn?rendered[anchor].z:a.z;
            const RouteView& tint=a;uint32_t seed=uint32_t(fx.id)^uint32_t(fxIndex*0x9e3779b9u);
            if(isRev){int count=24+int(28.f*activity);if(frame.active>12)count=std::max(18,count-10);
                for(int p=0;p<count;++p){uint32_t s=seed+uint32_t(p*0x85ebca6bu);float n0=noise01(s),n1=noise01(s+1),n2=noise01(s+2),n3=noise01(s+3);int b=std::clamp(lo+int(n0*float(hi-lo+1)),lo,hi);if(sh[b]<=.12f)continue;
                    float gain=std::pow(unit(sh[b]),.70f),phase=float(frame.timeMs*.00045)+6.2831853f*n1;float shell=.11f+.23f*gain+activity*(.08f+.13f*n2);
                    float px=pan+shell*std::cos(phase)*(1.15f+.45f*n2);float py=std::clamp(float(b)/75.f+(n3-.5f)*(.10f+.12f*activity),prefs.frequency.low,prefs.frequency.high);float pz=std::clamp(z+shell*.85f*std::sin(phase)+(.03f+.12f*n0)*activity,RoomFront,RoomBack);
                    auto q=project(px,py,pz,room);float size=2.8f+3.8f*n2;int alpha=int((70.f+125.f*activity)*(.65f+.35f*n3));SolidBrush particle(color(tint,alpha));g.FillEllipse(&particle,q.X-size*.5f,q.Y-size*.5f,size,size);}
            }else{int perEcho=7+int(5.f*activity);float dir=(anchor>=0?((anchor&1)?1.f:-1.f):1.f);
                for(int echo=1;echo<=3;++echo){float fade=1.f-float(echo-1)*.24f;for(int p=0;p<perEcho;++p){uint32_t s=seed+uint32_t(echo*211+p*31);float n0=noise01(s),n1=noise01(s+2),n2=noise01(s+5);int b=std::clamp(lo+int(n0*float(hi-lo+1)),lo,hi);if(sh[b]<=.12f)continue;
                        float px=pan+dir*(.14f+.045f*activity)*echo+(n1-.5f)*.10f;float py=std::clamp(float(b)/75.f+(n2-.5f)*.06f,prefs.frequency.low,prefs.frequency.high);float pz=std::clamp(z+(.105f+.04f*activity)*echo+(n0-.5f)*.05f,RoomFront,RoomBack);
                        auto q=project(px,py,pz,room);float size=3.f+3.2f*n1;int alpha=int((90.f+135.f*activity)*fade);SolidBrush particle(color(tint,alpha));g.FillRectangle(&particle,q.X-size*.5f,q.Y-size*.5f,size,size);}}
            }
        }
    }

    g.ResetClip();frequencyBar(g,client);if(order.empty()){float emptyX=float(room.left)+150.f;text(g,L"Play your session or show a source.",emptyX,290,620,46,Color(255,207,220,225),28,true);text(g,mode==L"FL Native"?L"Field maps the mixer routes exposed by FL Studio.":L"Play audio through the mixer routes exposed by the host.",emptyX,340,680,28,Color(255,117,145,159),14);}
    if(prefs.selected>=0&&prefs.selected<Routes&&frame.routes[prefs.selected].id){auto& v=frame.routes[prefs.selected];float x=float(client.right-365),y=float(client.bottom-255);SolidBrush panel(Color(245,21,31,39));g.FillRectangle(&panel,x,y,268.f,199.f);Pen edge(Color(255,49,67,78));g.DrawRectangle(&edge,x,y,268.f,199.f);
        Pen closePen(Color(255,146,164,173),1.4f);g.DrawLine(&closePen,x+242,y+12,x+255,y+25);g.DrawLine(&closePen,x+255,y+12,x+242,y+25);
        text(g,wide(v.name),x+16,y+12,214,27,color(v),16,true);text(g,wide(kindName(v.kind))+(v.sustained?L" / Sustained":L" / Transient"),x+16,y+44,236,23,Color(255,139,163,174),12);const auto& m=rendered[prefs.selected];float zz=m.drawn?m.z:v.z;
        float crest=(v.peak>-150&&v.rms>-150)?std::max(0.f,v.peak-v.rms):0.f;
        text(g,L"Pan "+number(v.pan*100,0)+L"   Width "+number(v.width*100,0)+L"%",x+16,y+75,240,22,Color(255,190,208,216),12);text(g,L"Depth "+number(zz,2)+L"    Dynamics "+number(crest,1)+L" dB",x+16,y+100,240,22,Color(255,190,208,216),12);
        text(g,number(v.low,0)+L" Hz - "+number(v.high,0)+L" Hz",x+16,y+125,240,22,Color(255,190,208,216),12);text(g,L"Peak "+number(v.peak)+L" dB   RMS "+number(v.rms)+L" dB",x+16,y+150,240,22,Color(255,139,163,174),11);}
    text(g,L"Drag to orbit    Scroll to zoom    Double-click to reset",float(room.left)+34,float(client.bottom-32),540,20,Color(255,96,122,138),11);
    if(diagnostics){text(g,L"Audio "+number(float(engine.callbackMs.load()),3)+L" ms   Analysis "+number(float(frame.analysisMs),2)+L" ms   Paint "+number(float(paintMs),2)+L" ms   "+number(float(fps),0)+L" FPS   Dropped "+std::to_wstring(frame.dropped),float(room.left)+24,77,900,22,Color(255,218,177,109),11);}
    Graphics target(dc);target.DrawImage(backBuffer.get(),0,0);EndPaint(hwnd,&ps);paintMs=nowMs()-start;if(lastPaint)fps=1000./std::max(1.,start-lastPaint);lastPaint=start;if(log&&start-lastLog>100){writeLog();lastLog=start;}
}
void View::exportLog(){if(log){fclose(log);log=nullptr;return;}wchar_t file[MAX_PATH]=L"Field-diagnostics.csv";OPENFILENAMEW ofn{};ofn.lStructSize=sizeof(ofn);ofn.hwndOwner=hwnd;ofn.lpstrFile=file;ofn.nMaxFile=MAX_PATH;
    ofn.lpstrFilter=L"CSV diagnostics\0*.csv\0\0";ofn.lpstrDefExt=L"csv";ofn.Flags=OFN_OVERWRITEPROMPT|OFN_PATHMUSTEXIST;
    if(GetSaveFileNameW(&ofn)&&_wfopen_s(&log,file,L"wb")==0&&log){setvbuf(log,nullptr,_IOFBF,1<<20);fprintf(log,"timestamp,route,route_name,route_type,peak_db,rms_db,presence,live_pan,stable_pan,render_pan,width,depth,voice_count,profile_ready,display_profile_ready,rendered,low_hz,high_hz,dominant_hz,onset_count,last_onset_ms,onset_to_visible_ms,reverb_amount,delay_amount,fx_confidence,fx_source,camera_yaw,camera_pitch,camera_zoom,frequency_low_hz,frequency_high_hz,audio_callback_ms,analysis_ms,paint_ms,fps,queue_depth,dropped_samples\n");}}
void View::writeLog(){if(!log)return;for(int i=0;i<Routes;++i){const auto& v=frame.routes[i];if(!heard(v))continue;auto& m=rendered[i];std::string name=v.name;size_t pos=0;while((pos=name.find('"',pos))!=std::string::npos){name.insert(pos,1,'"');pos+=2;}
    fprintf(log,"%.3f,%d,\"%s\",%s,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%d,%d,%d,%.2f,%.2f,%.2f,%u,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%.4f,%.4f,%.4f,%.2f,%.2f,%.4f,%.4f,%.4f,%.2f,%u,%llu\n",
        frame.timeMs,i+1,name.c_str(),kindName(v.kind),v.peak,v.rms,m.presence,v.pan,v.stablePan,m.pan,m.width,m.z,v.voices,int(v.ready),int(v.provisional),int(m.drawn),m.low,m.high,m.dominant,v.onsetCount,v.onsetMs,m.drawn?m.delay:-1.,v.reverb,v.delay,v.fxConfidence,v.fxSource>=0?v.fxSource+1:0,prefs.yaw,prefs.pitch,prefs.zoom,axisHz(prefs.frequency.low),axisHz(prefs.frequency.high),engine.callbackMs.load(),frame.analysisMs,paintMs,fps,frame.queueDepth,(unsigned long long)frame.dropped);}
    if(ferror(log)){fclose(log);log=nullptr;}}
}

