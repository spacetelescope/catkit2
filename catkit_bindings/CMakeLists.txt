cmake_minimum_required(VERSION 3.5)

project(catkit_bindings)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

set(SOURCES "bindings.cpp")

add_subdirectory(../extern/pybind11 pybind11)
pybind11_add_module(catkit_bindings ${SOURCES})

target_include_directories(catkit_bindings PUBLIC ../extern/pybind11_json-0.2.11/include)
target_include_directories(catkit_bindings PUBLIC ../catkit_core)

target_link_libraries(catkit_bindings PUBLIC catkit_core)

install(TARGETS catkit_bindings DESTINATION lib)
