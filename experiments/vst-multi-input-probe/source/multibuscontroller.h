#pragma once

#include "public.sdk/source/vst/vsteditcontroller.h"
#include "pluginterfaces/vst/ivstchannelcontextinfo.h"

#include <mutex>
#include <string>

namespace FieldMultiInputProbe {

class Controller : public Steinberg::Vst::EditControllerEx1,
                   public Steinberg::Vst::ChannelContext::IInfoListener
{
public:
    static Steinberg::FUnknown* createInstance (void*)
    {
        return static_cast<Steinberg::Vst::IEditController*> (new Controller);
    }

    Steinberg::tresult PLUGIN_API initialize (Steinberg::FUnknown* context) SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API setComponentState (Steinberg::IBStream* state) SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API setChannelContextInfos (Steinberg::Vst::IAttributeList* list) SMTG_OVERRIDE;
    Steinberg::IPlugView* PLUGIN_API createView (Steinberg::FIDString name) SMTG_OVERRIDE;

    std::string getCurrentChannel () const;

    OBJ_METHODS (Controller, Steinberg::Vst::EditControllerEx1)
    DEFINE_INTERFACES
        DEF_INTERFACE (Steinberg::Vst::ChannelContext::IInfoListener)
    END_DEFINE_INTERFACES (Steinberg::Vst::EditController)
    DELEGATE_REFCOUNT (Steinberg::Vst::EditControllerEx1)

private:
    mutable std::mutex stateMutex;
    std::string currentChannel {"not provided"};
};

} // namespace FieldMultiInputProbe
