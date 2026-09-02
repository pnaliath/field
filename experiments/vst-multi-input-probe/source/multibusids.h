#pragma once

#include "pluginterfaces/base/funknown.h"

namespace FieldMultiInputProbe {

static const Steinberg::FUID ProcessorUID (0x65E4A08D, 0x3217434C, 0xB9C72241, 0xE2AD8E9A);
static const Steinberg::FUID ControllerUID (0x2D743E12, 0xA63D4D09, 0x83E9F467, 0x7B51C8A4);

constexpr int kInputBusCount = 8;
constexpr int kStemOutputCount = 8;
constexpr int kTotalOutputBusCount = 1 + kStemOutputCount; // Mix + 8 independent stem outs

} // namespace FieldMultiInputProbe
