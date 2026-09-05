cmake_minimum_required(VERSION 3.22)
project(FieldV034RenderTruthDiagnostics VERSION 0.0.34 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
execute_process(
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/generate_v034.py
  RESULT_VARIABLE GEN_RESULT
)
if(NOT GEN_RESULT EQUAL 0)
  message(FATAL_ERROR "Failed to generate Field V0.34 source")
endif()

include(FetchContent)
FetchContent_Declare(
  flsdk_mirror
  GIT_REPOSITORY https://github.com/KennyTheBoss05/ModulatorX.git
  GIT_TAG 000ce2d64c46b302449d1462c7e3a34ed3a15415
  GIT_SHALLOW FALSE
)
FetchContent_GetProperties(flsdk_mirror)
if(NOT flsdk_mirror_POPULATED)
  FetchContent_Populate(flsdk_mirror)
endif()
set(FLSDK_DIR "${flsdk_mirror_SOURCE_DIR}/SDK")

add_library(FieldV034RenderTruthDiagnostics SHARED
  ${FLSDK_DIR}/fp_plugclass.cpp
  ${FLSDK_DIR}/fp_cplug.cpp
  ${FLSDK_DIR}/fp_extra.cpp
  ${FLSDK_DIR}/fp_pathmanager.cpp
  generated/fieldv034.cpp
)
target_include_directories(FieldV034RenderTruthDiagnostics PRIVATE ${FLSDK_DIR} generated)
target_compile_definitions(FieldV034RenderTruthDiagnostics PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX UNICODE _UNICODE _CRT_SECURE_NO_WARNINGS)
target_link_libraries(FieldV034RenderTruthDiagnostics PRIVATE gdiplus)
set_target_properties(FieldV034RenderTruthDiagnostics PROPERTIES
  PREFIX ""
  OUTPUT_NAME "Field V034 Render Truth Diagnostics_x64"
  SUFFIX ".dll"
)
if(MSVC)
  target_compile_options(FieldV034RenderTruthDiagnostics PRIVATE /W3 /EHsc)
endif()
