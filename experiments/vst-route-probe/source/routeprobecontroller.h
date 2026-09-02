#pragma once

#include "public.sdk/source/vst/vsteditcontroller.h"
#include "pluginterfaces/vst/ivstchannelcontextinfo.h"

#include <string>
#include <vector>

namespace FieldRouteProbe {

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

    OBJ_METHODS (Controller, Steinberg::Vst::EditControllerEx1)
    DEFINE_INTERFACES
        DEF_INTERFACE (Steinberg::Vst::ChannelContext::IInfoListener)
    END_DEFINE_INTERFACES (Steinberg::Vst::EditController)
    DELEGATE_REFCOUNT (Steinberg::Vst::EditControllerEx1)

private:
    void addReadOnlyString (const char16_t* title, Steinberg::Vst::ParamID id, const char* initial = "undefined");
    void setStringParam (Steinberg::Vst::ParamID id, const std::string& value);
    void rememberObservedName (const std::string& value);
    std::string joinedObservedNames () const;

    std::vector<std::string> observedNames;
    uint64_t callbackCount = 0;
};

} // namespace FieldRouteProbe
