#pragma once

#include "pluginterfaces/base/funknown.h"
#include "pluginterfaces/vst/vsttypes.h"

namespace FieldRouteProbe {

static const Steinberg::FUID ProcessorUID (0x173F632D, 0x8DE244E9, 0x9B26FC21, 0x176BB0A8);
static const Steinberg::FUID ControllerUID (0x2806B225, 0xA5B84710, 0x9713D848, 0x7CCF23F8);

enum ParamIds : Steinberg::Vst::ParamID
{
    kCurrentChannelName = 100,
    kObservedChannelNames,
    kCallbackCount,
    kChannelUID,
    kChannelRuntimeID,
    kChannelIndex,
    kIndexNamespace,
    kPluginLocation,
    kChannelColor,
    kRoutingProbeResult
};

} // namespace FieldRouteProbe
