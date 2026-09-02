cmake_minimum_required(VERSION 3.25)

project(FieldMultiInputProbe
    VERSION 0.1.0.0
    DESCRIPTION "Single-instance multi-input VST3 routing probe for Field"
)

include(FetchContent)

set(SMTG_ENABLE_VST3_PLUGIN_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SMTG_ENABLE_VST3_HOSTING_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SMTG_ENABLE_VSTGUI_SUPPORT OFF CACHE BOOL "" FORCE)
set(SMTG_CREATE_PLUGIN_LINK OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
    vst3sdk
    GIT_REPOSITORY https://github.com/steinbergmedia/vst3sdk.git
    GIT_TAG 9fad9770f2ae8542ab1a548a68c1ad1ac690abe0
    GIT_SHALLOW FALSE
    GIT_SUBMODULES_RECURSE TRUE
)
FetchContent_MakeAvailable(vst3sdk)

smtg_add_vst3plugin(FieldMultiInputProbe
    source/multibusprocessor.cpp
    source/multibusprocessor.h
    source/multibuscontroller.cpp
    source/multibuscontroller.h
    source/multibusview.cpp
    source/multibusview.h
    source/multibusstate.h
    source/multibusids.h
    source/factory.cpp
    source/version.h
)

target_link_libraries(FieldMultiInputProbe PRIVATE sdk)
if(WIN32)
    target_link_libraries(FieldMultiInputProbe PRIVATE user32 gdi32)
endif()

target_compile_features(FieldMultiInputProbe PRIVATE cxx_std_17)
smtg_target_configure_version_file(FieldMultiInputProbe)
