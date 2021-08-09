cmake_minimum_required(VERSION 3.0)

project(catkit2)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

add_subdirectory(lib/data_streams_core)
add_subdirectory(lib/pybind11)

set(SOURCE_DIR "catkit2")

set(SOURCES "${SOURCE_DIR}/data_streams_core_bindings.cpp")

pybind11_add_module(data_streams ${SOURCES})

target_link_libraries(data_streams PRIVATE data_streams_core)
