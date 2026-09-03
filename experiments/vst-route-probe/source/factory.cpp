#include "routeprobecontroller.h"
#include "routeprobeids.h"
#include "routeprobeprocessor.h"
#include "version.h"

#include "public.sdk/source/main/pluginfactory.h"

using namespace Steinberg;
using namespace Steinberg::Vst;

#define stringPluginName "Field Route Probe"

BEGIN_FACTORY_DEF (stringCompanyName, stringCompanyWeb, stringCompanyEmail)

DEF_CLASS2 (INLINE_UID_FROM_FUID (FieldRouteProbe::ProcessorUID),
            PClassInfo::kManyInstances,
            kVstAudioEffectClass,
            stringPluginName,
            Vst::kDistributable,
            "Fx|Analyzer",
            FULL_VERSION_STR,
            kVstVersionString,
            FieldRouteProbe::Processor::createInstance)

DEF_CLASS2 (INLINE_UID_FROM_FUID (FieldRouteProbe::ControllerUID),
            PClassInfo::kManyInstances,
            kVstComponentControllerClass,
            stringPluginName " Controller",
            0,
            "",
            FULL_VERSION_STR,
            kVstVersionString,
            FieldRouteProbe::Controller::createInstance)

END_FACTORY
