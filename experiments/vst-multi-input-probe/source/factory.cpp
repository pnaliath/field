#include "multibuscontroller.h"
#include "multibusids.h"
#include "multibusprocessor.h"
#include "version.h"

#include "public.sdk/source/main/pluginfactory.h"

using namespace Steinberg;
using namespace Steinberg::Vst;

#define stringPluginName "Field Multi-Input Probe"

BEGIN_FACTORY_DEF (stringCompanyName, stringCompanyWeb, stringCompanyEmail)

DEF_CLASS2 (INLINE_UID_FROM_FUID (FieldMultiInputProbe::ProcessorUID),
            PClassInfo::kManyInstances,
            kVstAudioEffectClass,
            stringPluginName,
            Vst::kDistributable,
            "Fx|Analyzer|Spatial",
            FULL_VERSION_STR,
            kVstVersionString,
            FieldMultiInputProbe::Processor::createInstance)

DEF_CLASS2 (INLINE_UID_FROM_FUID (FieldMultiInputProbe::ControllerUID),
            PClassInfo::kManyInstances,
            kVstComponentControllerClass,
            stringPluginName " Controller",
            0,
            "",
            FULL_VERSION_STR,
            kVstVersionString,
            FieldMultiInputProbe::Controller::createInstance)

END_FACTORY
