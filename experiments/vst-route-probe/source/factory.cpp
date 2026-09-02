#include "routeprobecontroller.h"
#include "routeprobeids.h"
#include "routeprobeprocessor.h"
#include "version.h"

#include "public.sdk/source/main/pluginfactory_constexpr.h"

using namespace Steinberg;
using namespace Steinberg::Vst;

#define stringPluginName "Field Route Probe"

BEGIN_FACTORY_DEF (stringCompanyName, stringCompanyWeb, stringCompanyEmail, 2)

DEF_CLASS (FieldRouteProbe::ProcessorUID,
           PClassInfo::kManyInstances,
           kVstAudioEffectClass,
           stringPluginName,
           Vst::kDistributable,
           "Fx|Analyzer",
           FULL_VERSION_STR,
           kVstVersionString,
           FieldRouteProbe::Processor::createInstance,
           nullptr)

DEF_CLASS (FieldRouteProbe::ControllerUID,
           PClassInfo::kManyInstances,
           kVstComponentControllerClass,
           stringPluginName " Controller",
           0,
           "",
           FULL_VERSION_STR,
           kVstVersionString,
           FieldRouteProbe::Controller::createInstance,
           nullptr)

END_FACTORY
