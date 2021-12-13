cmake_minimum_required(VERSION 3.0)

project(catkit2)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

add_subdirectory(catkit_core)
add_subdirectory(catkit_bindings)
