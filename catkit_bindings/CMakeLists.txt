cmake_minimum_required(VERSION 3.5)

project(catkit_bindings)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

set(SOURCES "bindings.cpp")

find_package(pybind11 REQUIRED)
pybind11_add_module(catkit_bindings ${SOURCES})

find_package(pybind11_json REQUIRED)
target_include_directories(catkit_bindings PUBLIC pybind11_json_INCLUDE_DIRS)

target_include_directories(catkit_bindings PUBLIC ../catkit_core)

target_link_libraries(catkit_bindings PUBLIC catkit_core)

install(TARGETS catkit_bindings DESTINATION lib)
