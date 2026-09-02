#include "multibuscontroller.h"
#include "multibusview.h"

#include "public.sdk/source/vst/utility/stringconvert.h"

#include <cstring>

namespace FieldMultiInputProbe {

using namespace Steinberg;
using namespace Steinberg::Vst;

tresult PLUGIN_API Controller::initialize (FUnknown* context)
{
    return EditControllerEx1::initialize (context);
}

tresult PLUGIN_API Controller::setComponentState (IBStream*)
{
    return kResultOk;
}

IPlugView* PLUGIN_API Controller::createView (FIDString name)
{
    if (name && std::strcmp (name, ViewType::kEditor) == 0)
        return new MultiBusView (this);
    return nullptr;
}

tresult PLUGIN_API Controller::setChannelContextInfos (IAttributeList* list)
{
    if (!list)
        return kResultFalse;

    String128 text {};
    if (list->getString (ChannelContext::kChannelNameKey, text, sizeof (text)) == kResultTrue)
    {
        std::lock_guard<std::mutex> lock (stateMutex);
        currentChannel = StringConvert::convert (text);
    }
    return kResultTrue;
}

std::string Controller::getCurrentChannel () const
{
    std::lock_guard<std::mutex> lock (stateMutex);
    return currentChannel;
}

} // namespace FieldMultiInputProbe
