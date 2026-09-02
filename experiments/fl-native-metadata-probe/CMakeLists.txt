cmake_minimum_required(VERSION 3.22)
project(FieldFLMetadataProbe VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# EXPERIMENT ONLY: fetch a public mirror containing Image-Line's public FL Studio SDK.
# Before any commercial distribution, replace this dependency with the SDK downloaded
# directly from https://www.image-line.com/developers and review its current license.
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

add_library(FieldFLMetadataProbe SHARED
    ${FLSDK_DIR}/fp_plugclass.cpp
    ${FLSDK_DIR}/fp_cplug.cpp
    ${FLSDK_DIR}/fp_extra.cpp
    ${FLSDK_DIR}/fp_pathmanager.cpp
    source/fieldflprobe.cpp
)

target_include_directories(FieldFLMetadataProbe PRIVATE
    ${FLSDK_DIR}
    source
)

target_compile_definitions(FieldFLMetadataProbe PRIVATE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
)

set_target_properties(FieldFLMetadataProbe PROPERTIES
    PREFIX ""
    OUTPUT_NAME "Field FL Metadata Probe_x64"
    SUFFIX ".dll"
)

if(MSVC)
    target_compile_options(FieldFLMetadataProbe PRIVATE /W3 /EHsc)
endif()
