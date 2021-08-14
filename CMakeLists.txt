cmake_minimum_required(VERSION 3.0)

project(catkit2)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

add_subdirectory(lib/catkit-core)
add_subdirectory(extern/pybind11)

set(SOURCEDIR "catkit2")

set(SOURCES "${SOURCEDIR}/core_bindings.cpp")

pybind11_add_module(core ${SOURCES})

target_link_libraries(core PRIVATE catkit-core)
