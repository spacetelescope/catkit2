cmake_minimum_required(VERSION 3.0)

project(catkit2)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

set(SOURCES "bindings.cpp")

add_subdirectory(../extern/pybind11 pybind11)
pybind11_add_module(bindings ${SOURCES})

target_include_directories(bindings PUBLIC ../extern/pybind11_json-0.2.11/include)

set_target_properties(bindings PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    LIBRARY_OUTPUT_DIRECTORY_RELEASE "${CMAKE_CURRENT_SOURCE_DIR}"
    LIBRARY_OUTPUT_DIRECTORY_DEBUG "${CMAKE_CURRENT_SOURCE_DIR}")

target_link_libraries(bindings PUBLIC catkit_core)
