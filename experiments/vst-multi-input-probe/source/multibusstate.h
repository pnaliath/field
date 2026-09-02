#pragma once

#include "multibusids.h"

#include <array>
#include <atomic>
#include <cstdint>

namespace FieldMultiInputProbe {

struct SharedProbeState
{
    SharedProbeState ()
    {
        for (int i = 0; i < kInputBusCount; ++i)
        {
            rmsDb[i].store (-120.0f);
            peakDb[i].store (-120.0f);
            signalSeen[i].store (0);
        }
    }

    std::array<std::atomic<float>, kInputBusCount> rmsDb;
    std::array<std::atomic<float>, kInputBusCount> peakDb;
    std::array<std::atomic<uint64_t>, kInputBusCount> signalSeen;
    std::atomic<uint64_t> processBlocks {0};
    std::atomic<int> numInputsSeen {0};
    std::atomic<int> numOutputsSeen {0};
};

inline SharedProbeState& sharedProbeState ()
{
    static SharedProbeState state;
    return state;
}

} // namespace FieldMultiInputProbe
