cmake_minimum_required(VERSION 3.5)

project(catkit2)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

# Ensure that conda-installed libraries take precedence over
# system installed libraries.
list(APPEND CMAKE_PREFIX_PATH "$ENV{CONDA_PREFIX}")
list(APPEND CMAKE_PREFIX_PATH "$ENV{CONDA_PREFIX}/Library")

add_subdirectory(catkit_core)
add_subdirectory(catkit_bindings)
add_subdirectory(benchmarks)
