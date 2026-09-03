#include <windows.h>

#ifndef GET_X_LPARAM
#define GET_X_LPARAM(lp) (static_cast<int>(static_cast<short>(LOWORD(lp))))
#endif
#ifndef GET_Y_LPARAM
#define GET_Y_LPARAM(lp) (static_cast<int>(static_cast<short>(HIWORD(lp))))
#endif

// Build shim for Field V0.02. The implementation lives in fieldflprobe.cpp;
// these coordinate helpers are normally supplied by windowsx.h, but keeping
// them local avoids another SDK/platform dependency in the experiment.
#include "fieldflprobe.cpp"
