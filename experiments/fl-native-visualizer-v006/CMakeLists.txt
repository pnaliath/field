cmake_minimum_required(VERSION 3.22)
project(FieldV006FxAwareVisualizer VERSION 0.0.6 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
execute_process(
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/generate_v006_fixed3.py
    RESULT_VARIABLE GEN_RESULT
)
if(NOT GEN_RESULT EQUAL 0)
    message(FATAL_ERROR "Failed to generate Field V0.06 source")
endif()

include(FetchContent)
FetchContent_Declare(
    flsdk_mirror
    GIT_REPOSITORY https://github.com/KennyTheBoss05/ModulatorX.git
    GIT_TAG        000ce2d64c46b302449d1462c7e3a34ed3a15415
    GIT_SHALLOW    FALSE
)
FetchContent_GetProperties(flsdk_mirror)
if(NOT flsdk_mirror_POPULATED)
    FetchContent_Populate(flsdk_mirror)
endif()

set(FLSDK_DIR "${flsdk_mirror_SOURCE_DIR}/SDK")

add_library(FieldV006FxAwareVisualizer SHARED
    ${FLSDK_DIR}/fp_plugclass.cpp
    ${FLSDK_DIR}/fp_cplug.cpp
    ${FLSDK_DIR}/fp_extra.cpp
    ${FLSDK_DIR}/fp_pathmanager.cpp
    generated/fieldv006.cpp
)

target_include_directories(FieldV006FxAwareVisualizer PRIVATE
    ${FLSDK_DIR}
    generated
)

target_compile_definitions(FieldV006FxAwareVisualizer PRIVATE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
    UNICODE
    _UNICODE
    _CRT_SECURE_NO_WARNINGS
)

set_target_properties(FieldV006FxAwareVisualizer PROPERTIES
    PREFIX ""
    OUTPUT_NAME "Field V006 FX Aware Visualizer_x64"
    SUFFIX ".dll"
)

if(MSVC)
    target_compile_options(FieldV006FxAwareVisualizer PRIVATE /W3 /EHsc)
endif()
