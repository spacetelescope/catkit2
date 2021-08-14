cmake_minimum_required(VERSION 3.0)

project(catkit2)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

add_subdirectory(lib/data_streams_core)
add_subdirectory(extern/pybind11)

set(SOURCEDIR "catkit2")

set(SOURCES "${SOURCEDIR}/data_streams_core_bindings.cpp")

pybind11_add_module(data_streams ${SOURCES})

target_link_libraries(data_streams PRIVATE data_streams_core)
