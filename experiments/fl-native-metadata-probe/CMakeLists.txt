cmake_minimum_required(VERSION 3.22)
project(FieldV003ReconstructProbe VERSION 0.0.3 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# EXPERIMENT ONLY: fetch a public mirror containing Image-Line's public FL Studio SDK.
# Before commercial distribution, replace this dependency with the SDK downloaded
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

add_library(FieldV003ReconstructProbe SHARED
    ${FLSDK_DIR}/fp_plugclass.cpp
    ${FLSDK_DIR}/fp_cplug.cpp
    ${FLSDK_DIR}/fp_extra.cpp
    ${FLSDK_DIR}/fp_pathmanager.cpp
    source/fieldv003.cpp
)

target_include_directories(FieldV003ReconstructProbe PRIVATE
    ${FLSDK_DIR}
    source
)

target_compile_definitions(FieldV003ReconstructProbe PRIVATE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
    UNICODE
    _UNICODE
    _CRT_SECURE_NO_WARNINGS
)

set_target_properties(FieldV003ReconstructProbe PROPERTIES
    PREFIX ""
    # Keep the filesystem identity dot-free to avoid native-loader ambiguity.
    # The plugin's reported/UI name remains "Field V0.03 Reconstruct Probe".
    OUTPUT_NAME "Field V003 Reconstruct Probe_x64"
    SUFFIX ".dll"
)

if(MSVC)
    target_compile_options(FieldV003ReconstructProbe PRIVATE /W3 /EHsc)
endif()
