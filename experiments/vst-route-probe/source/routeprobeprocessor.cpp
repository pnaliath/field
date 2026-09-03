#include "routeprobeprocessor.h"
#include "routeprobeids.h"

#include "pluginterfaces/vst/vstspeaker.h"

#include <algorithm>
#include <cstring>

namespace FieldRouteProbe {

using namespace Steinberg;
using namespace Steinberg::Vst;

Processor::Processor ()
{
    setControllerClass (ControllerUID);
}

tresult PLUGIN_API Processor::initialize (FUnknown* context)
{
    const auto result = AudioEffect::initialize (context);
    if (result != kResultOk)
        return result;

    addAudioInput  (STR16 ("Input"),  SpeakerArr::kStereo);
    addAudioOutput (STR16 ("Output"), SpeakerArr::kStereo);
    return kResultOk;
}

tresult PLUGIN_API Processor::canProcessSampleSize (int32 symbolicSampleSize)
{
    return (symbolicSampleSize == kSample32 || symbolicSampleSize == kSample64)
        ? kResultTrue : kResultFalse;
}

tresult PLUGIN_API Processor::process (ProcessData& data)
{
    if (data.numInputs < 1 || data.numOutputs < 1)
        return kResultOk;

    const auto channels = std::min (data.inputs[0].numChannels, data.outputs[0].numChannels);
    data.outputs[0].silenceFlags = data.inputs[0].silenceFlags;

    if (data.symbolicSampleSize == kSample64)
    {
        auto** in  = data.inputs[0].channelBuffers64;
        auto** out = data.outputs[0].channelBuffers64;
        for (int32 c = 0; c < channels; ++c)
            if (in[c] != out[c])
                std::memcpy (out[c], in[c], static_cast<size_t> (data.numSamples) * sizeof (double));
        for (int32 c = channels; c < data.outputs[0].numChannels; ++c)
            std::memset (out[c], 0, static_cast<size_t> (data.numSamples) * sizeof (double));
    }
    else
    {
        auto** in  = data.inputs[0].channelBuffers32;
        auto** out = data.outputs[0].channelBuffers32;
        for (int32 c = 0; c < channels; ++c)
            if (in[c] != out[c])
                std::memcpy (out[c], in[c], static_cast<size_t> (data.numSamples) * sizeof (float));
        for (int32 c = channels; c < data.outputs[0].numChannels; ++c)
            std::memset (out[c], 0, static_cast<size_t> (data.numSamples) * sizeof (float));
    }

    return kResultOk;
}

tresult PLUGIN_API Processor::setState (IBStream*)
{
    return kResultOk;
}

tresult PLUGIN_API Processor::getState (IBStream*)
{
    return kResultOk;
}

} // namespace FieldRouteProbe
