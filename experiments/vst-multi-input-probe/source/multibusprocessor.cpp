#include "multibusprocessor.h"
#include "multibusids.h"
#include "multibusstate.h"

#include "pluginterfaces/vst/vstspeaker.h"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace FieldMultiInputProbe {

using namespace Steinberg;
using namespace Steinberg::Vst;

namespace {

float toDb (double linear)
{
    return static_cast<float> (20.0 * std::log10 (std::max (linear, 1.0e-6)));
}

void clear32 (AudioBusBuffers& bus, int32 samples)
{
    if (!bus.channelBuffers32)
        return;
    for (int32 c = 0; c < bus.numChannels; ++c)
        if (bus.channelBuffers32[c])
            std::memset (bus.channelBuffers32[c], 0, static_cast<size_t> (samples) * sizeof (Sample32));
    bus.silenceFlags = bus.numChannels >= 64 ? ~uint64 (0) : ((uint64 (1) << bus.numChannels) - 1);
}

void clear64 (AudioBusBuffers& bus, int32 samples)
{
    if (!bus.channelBuffers64)
        return;
    for (int32 c = 0; c < bus.numChannels; ++c)
        if (bus.channelBuffers64[c])
            std::memset (bus.channelBuffers64[c], 0, static_cast<size_t> (samples) * sizeof (Sample64));
    bus.silenceFlags = bus.numChannels >= 64 ? ~uint64 (0) : ((uint64 (1) << bus.numChannels) - 1);
}

void copy32 (const AudioBusBuffers& in, AudioBusBuffers& out, int32 samples)
{
    if (!in.channelBuffers32 || !out.channelBuffers32)
        return;
    const int32 channels = std::min (in.numChannels, out.numChannels);
    for (int32 c = 0; c < channels; ++c)
    {
        if (!in.channelBuffers32[c] || !out.channelBuffers32[c])
            continue;
        if (in.channelBuffers32[c] != out.channelBuffers32[c])
            std::memcpy (out.channelBuffers32[c], in.channelBuffers32[c], static_cast<size_t> (samples) * sizeof (Sample32));
    }
    for (int32 c = channels; c < out.numChannels; ++c)
        if (out.channelBuffers32[c])
            std::memset (out.channelBuffers32[c], 0, static_cast<size_t> (samples) * sizeof (Sample32));
    out.silenceFlags = in.silenceFlags;
}

void copy64 (const AudioBusBuffers& in, AudioBusBuffers& out, int32 samples)
{
    if (!in.channelBuffers64 || !out.channelBuffers64)
        return;
    const int32 channels = std::min (in.numChannels, out.numChannels);
    for (int32 c = 0; c < channels; ++c)
    {
        if (!in.channelBuffers64[c] || !out.channelBuffers64[c])
            continue;
        if (in.channelBuffers64[c] != out.channelBuffers64[c])
            std::memcpy (out.channelBuffers64[c], in.channelBuffers64[c], static_cast<size_t> (samples) * sizeof (Sample64));
    }
    for (int32 c = channels; c < out.numChannels; ++c)
        if (out.channelBuffers64[c])
            std::memset (out.channelBuffers64[c], 0, static_cast<size_t> (samples) * sizeof (Sample64));
    out.silenceFlags = in.silenceFlags;
}

void analyse32 (const AudioBusBuffers& in, int32 samples, float& rmsDb, float& peakDb)
{
    if (!in.channelBuffers32 || in.numChannels <= 0 || samples <= 0)
    {
        rmsDb = peakDb = -120.0f;
        return;
    }

    double sumSq = 0.0;
    double peak = 0.0;
    uint64_t count = 0;
    for (int32 c = 0; c < in.numChannels; ++c)
    {
        const auto* p = in.channelBuffers32[c];
        if (!p)
            continue;
        for (int32 n = 0; n < samples; ++n)
        {
            const double v = p[n];
            sumSq += v * v;
            peak = std::max (peak, std::abs (v));
            ++count;
        }
    }
    const double rms = count ? std::sqrt (sumSq / static_cast<double> (count)) : 0.0;
    rmsDb = toDb (rms);
    peakDb = toDb (peak);
}

void analyse64 (const AudioBusBuffers& in, int32 samples, float& rmsDb, float& peakDb)
{
    if (!in.channelBuffers64 || in.numChannels <= 0 || samples <= 0)
    {
        rmsDb = peakDb = -120.0f;
        return;
    }

    long double sumSq = 0.0;
    double peak = 0.0;
    uint64_t count = 0;
    for (int32 c = 0; c < in.numChannels; ++c)
    {
        const auto* p = in.channelBuffers64[c];
        if (!p)
            continue;
        for (int32 n = 0; n < samples; ++n)
        {
            const double v = p[n];
            sumSq += static_cast<long double> (v) * static_cast<long double> (v);
            peak = std::max (peak, std::abs (v));
            ++count;
        }
    }
    const double rms = count ? std::sqrt (static_cast<double> (sumSq / static_cast<long double> (count))) : 0.0;
    rmsDb = toDb (rms);
    peakDb = toDb (peak);
}

void addToMix32 (const AudioBusBuffers& in, AudioBusBuffers& mix, int32 samples)
{
    if (!in.channelBuffers32 || !mix.channelBuffers32)
        return;
    const int32 channels = std::min (in.numChannels, mix.numChannels);
    for (int32 c = 0; c < channels; ++c)
    {
        const auto* src = in.channelBuffers32[c];
        auto* dst = mix.channelBuffers32[c];
        if (!src || !dst)
            continue;
        for (int32 n = 0; n < samples; ++n)
            dst[n] += src[n];
    }
    mix.silenceFlags = 0;
}

void addToMix64 (const AudioBusBuffers& in, AudioBusBuffers& mix, int32 samples)
{
    if (!in.channelBuffers64 || !mix.channelBuffers64)
        return;
    const int32 channels = std::min (in.numChannels, mix.numChannels);
    for (int32 c = 0; c < channels; ++c)
    {
        const auto* src = in.channelBuffers64[c];
        auto* dst = mix.channelBuffers64[c];
        if (!src || !dst)
            continue;
        for (int32 n = 0; n < samples; ++n)
            dst[n] += src[n];
    }
    mix.silenceFlags = 0;
}

} // namespace

Processor::Processor ()
{
    setControllerClass (ControllerUID);
}

tresult PLUGIN_API Processor::initialize (FUnknown* context)
{
    const auto result = AudioEffect::initialize (context);
    if (result != kResultOk)
        return result;

    addAudioInput (STR16 ("Field Input 1 (Main)"), SpeakerArr::kStereo, BusTypes::kMain);
    addAudioInput (STR16 ("Field Input 2"),        SpeakerArr::kStereo, BusTypes::kAux);
    addAudioInput (STR16 ("Field Input 3"),        SpeakerArr::kStereo, BusTypes::kAux);
    addAudioInput (STR16 ("Field Input 4"),        SpeakerArr::kStereo, BusTypes::kAux);
    addAudioInput (STR16 ("Field Input 5"),        SpeakerArr::kStereo, BusTypes::kAux);
    addAudioInput (STR16 ("Field Input 6"),        SpeakerArr::kStereo, BusTypes::kAux);
    addAudioInput (STR16 ("Field Input 7"),        SpeakerArr::kStereo, BusTypes::kAux);
    addAudioInput (STR16 ("Field Input 8"),        SpeakerArr::kStereo, BusTypes::kAux);

    // Output 0 is a monitor mix of all active inputs. Outputs 1..8 mirror each input separately.
    addAudioOutput (STR16 ("Field Mix"),           SpeakerArr::kStereo, BusTypes::kMain);
    addAudioOutput (STR16 ("Stem Out 1"),          SpeakerArr::kStereo, BusTypes::kAux);
    addAudioOutput (STR16 ("Stem Out 2"),          SpeakerArr::kStereo, BusTypes::kAux);
    addAudioOutput (STR16 ("Stem Out 3"),          SpeakerArr::kStereo, BusTypes::kAux);
    addAudioOutput (STR16 ("Stem Out 4"),          SpeakerArr::kStereo, BusTypes::kAux);
    addAudioOutput (STR16 ("Stem Out 5"),          SpeakerArr::kStereo, BusTypes::kAux);
    addAudioOutput (STR16 ("Stem Out 6"),          SpeakerArr::kStereo, BusTypes::kAux);
    addAudioOutput (STR16 ("Stem Out 7"),          SpeakerArr::kStereo, BusTypes::kAux);
    addAudioOutput (STR16 ("Stem Out 8"),          SpeakerArr::kStereo, BusTypes::kAux);

    return kResultOk;
}

tresult PLUGIN_API Processor::canProcessSampleSize (int32 symbolicSampleSize)
{
    return (symbolicSampleSize == kSample32 || symbolicSampleSize == kSample64)
        ? kResultTrue : kResultFalse;
}

tresult PLUGIN_API Processor::process (ProcessData& data)
{
    auto& state = sharedProbeState ();
    const auto blockNumber = state.processBlocks.fetch_add (1) + 1;
    state.numInputsSeen.store (data.numInputs);
    state.numOutputsSeen.store (data.numOutputs);

    for (int i = 0; i < kInputBusCount; ++i)
    {
        state.rmsDb[i].store (-120.0f);
        state.peakDb[i].store (-120.0f);
    }

    const int32 inputCount = std::min<int32> (data.numInputs, kInputBusCount);

    if (data.symbolicSampleSize == kSample64)
    {
        // First copy each independent input to its corresponding stem output.
        for (int32 i = 0; i < inputCount; ++i)
        {
            float rms = -120.0f, peak = -120.0f;
            analyse64 (data.inputs[i], data.numSamples, rms, peak);
            state.rmsDb[i].store (rms);
            state.peakDb[i].store (peak);
            if (peak > -90.0f)
                state.signalSeen[i].store (blockNumber);

            const int32 stemOutput = i + 1;
            if (stemOutput < data.numOutputs)
            {
                clear64 (data.outputs[stemOutput], data.numSamples);
                copy64 (data.inputs[i], data.outputs[stemOutput], data.numSamples);
            }
        }

        // Clear unused stem outputs.
        for (int32 o = inputCount + 1; o < data.numOutputs; ++o)
            clear64 (data.outputs[o], data.numSamples);

        // Main output is an unattenuated monitor sum of all Field inputs.
        if (data.numOutputs > 0)
        {
            auto& mix = data.outputs[0];
            if (inputCount > 0 && data.inputs[0].channelBuffers64)
                copy64 (data.inputs[0], mix, data.numSamples);
            else
                clear64 (mix, data.numSamples);

            for (int32 i = 1; i < inputCount; ++i)
                addToMix64 (data.inputs[i], mix, data.numSamples);
        }
    }
    else
    {
        for (int32 i = 0; i < inputCount; ++i)
        {
            float rms = -120.0f, peak = -120.0f;
            analyse32 (data.inputs[i], data.numSamples, rms, peak);
            state.rmsDb[i].store (rms);
            state.peakDb[i].store (peak);
            if (peak > -90.0f)
                state.signalSeen[i].store (blockNumber);

            const int32 stemOutput = i + 1;
            if (stemOutput < data.numOutputs)
            {
                clear32 (data.outputs[stemOutput], data.numSamples);
                copy32 (data.inputs[i], data.outputs[stemOutput], data.numSamples);
            }
        }

        for (int32 o = inputCount + 1; o < data.numOutputs; ++o)
            clear32 (data.outputs[o], data.numSamples);

        if (data.numOutputs > 0)
        {
            auto& mix = data.outputs[0];
            if (inputCount > 0 && data.inputs[0].channelBuffers32)
                copy32 (data.inputs[0], mix, data.numSamples);
            else
                clear32 (mix, data.numSamples);

            for (int32 i = 1; i < inputCount; ++i)
                addToMix32 (data.inputs[i], mix, data.numSamples);
        }
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

} // namespace FieldMultiInputProbe
