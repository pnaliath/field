#include "routeprobecontroller.h"
#include "routeprobeids.h"

#include "pluginterfaces/base/ustring.h"
#include "public.sdk/source/vst/utility/stringconvert.h"

#include <algorithm>
#include <cstdio>

namespace FieldRouteProbe {

using namespace Steinberg;
using namespace Steinberg::Vst;

void Controller::addReadOnlyString (const TChar* title, ParamID id, const char* initial)
{
    auto* param = NEW StringListParameter (title, id, nullptr, ParameterInfo::kIsReadOnly);
    String128 text {};
    StringConvert::convert (initial, text);
    param->appendString (text);
    parameters.addParameter (param);
}

void Controller::setStringParam (ParamID id, const std::string& value)
{
    auto* param = static_cast<StringListParameter*> (parameters.getParameter (id));
    if (!param)
        return;

    String128 text {};
    auto clipped = value.substr (0, 120);
    StringConvert::convert (clipped, text);
    param->replaceString (0, text);
}

void Controller::rememberObservedName (const std::string& value)
{
    if (value.empty ())
        return;

    if (std::find (observedNames.begin (), observedNames.end (), value) == observedNames.end ())
        observedNames.push_back (value);
}

std::string Controller::joinedObservedNames () const
{
    if (observedNames.empty ())
        return "none observed";

    std::string out;
    for (const auto& name : observedNames)
    {
        if (!out.empty ())
            out += " | ";
        out += name;
        if (out.size () > 112)
        {
            out.resize (109);
            out += "...";
            break;
        }
    }
    return out;
}

tresult PLUGIN_API Controller::initialize (FUnknown* context)
{
    auto result = EditControllerEx1::initialize (context);
    if (result != kResultOk)
        return result;

    addReadOnlyString (STR16 ("Current channel"),       kCurrentChannelName, "not provided yet");
    addReadOnlyString (STR16 ("All names observed"),    kObservedChannelNames, "none observed");
    addReadOnlyString (STR16 ("Context callbacks"),     kCallbackCount, "0");
    addReadOnlyString (STR16 ("Channel UID"),           kChannelUID, "not provided");
    addReadOnlyString (STR16 ("Channel runtime ID"),    kChannelRuntimeID, "not provided");
    addReadOnlyString (STR16 ("Channel index"),         kChannelIndex, "not provided");
    addReadOnlyString (STR16 ("Index namespace"),       kIndexNamespace, "not provided");
    addReadOnlyString (STR16 ("Plugin location"),       kPluginLocation, "not provided");
    addReadOnlyString (STR16 ("Channel colour ARGB"),   kChannelColor, "not provided");
    addReadOnlyString (STR16 ("Upstream-route probe"),  kRoutingProbeResult,
                       "VST3 exposes this instance channel, not its upstream routing graph");

    return kResultOk;
}

tresult PLUGIN_API Controller::setComponentState (IBStream*)
{
    return kResultOk;
}

tresult PLUGIN_API Controller::setChannelContextInfos (IAttributeList* list)
{
    if (!list)
        return kResultFalse;

    ++callbackCount;
    setStringParam (kCallbackCount, std::to_string (callbackCount));

    String128 text {};
    if (list->getString (ChannelContext::kChannelNameKey, text, sizeof (text)) == kResultTrue)
    {
        const auto name = StringConvert::convert (text);
        setStringParam (kCurrentChannelName, name);
        rememberObservedName (name);
        setStringParam (kObservedChannelNames, joinedObservedNames ());
    }

    if (list->getString (ChannelContext::kChannelUIDKey, text, sizeof (text)) == kResultTrue)
        setStringParam (kChannelUID, StringConvert::convert (text));

    int64 value = 0;
    if (list->getInt (ChannelContext::kChannelRuntimeIDKey, value) == kResultTrue)
        setStringParam (kChannelRuntimeID, std::to_string (value));

    if (list->getInt (ChannelContext::kChannelIndexKey, value) == kResultTrue)
        setStringParam (kChannelIndex, std::to_string (value));

    if (list->getString (ChannelContext::kChannelIndexNamespaceKey, text, sizeof (text)) == kResultTrue)
        setStringParam (kIndexNamespace, StringConvert::convert (text));

    if (list->getInt (ChannelContext::kChannelPluginLocationKey, value) == kResultTrue)
    {
        switch (value)
        {
            case ChannelContext::kPreVolumeFader:  setStringParam (kPluginLocation, "pre-volume fader"); break;
            case ChannelContext::kPostVolumeFader: setStringParam (kPluginLocation, "post-volume fader"); break;
            case ChannelContext::kUsedAsPanner:    setStringParam (kPluginLocation, "used as panner"); break;
            default:                               setStringParam (kPluginLocation, "other/unknown: " + std::to_string (value)); break;
        }
    }

    if (list->getInt (ChannelContext::kChannelColorKey, value) == kResultTrue)
    {
        const auto colour = static_cast<uint32> (value);
        char hex[16] {};
        std::snprintf (hex, sizeof (hex), "#%02X%02X%02X%02X",
                       ChannelContext::GetAlpha (colour), ChannelContext::GetRed (colour),
                       ChannelContext::GetGreen (colour), ChannelContext::GetBlue (colour));
        setStringParam (kChannelColor, hex);
    }

    if (componentHandler)
        componentHandler->restartComponent (kParamValuesChanged);

    return kResultTrue;
}

} // namespace FieldRouteProbe
