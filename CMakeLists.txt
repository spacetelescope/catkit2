cmake_minimum_required(VERSION 3.21)

project(catkit2)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED on)

# Add debug symbols for all builds.
if (MSVC)
    add_compile_options("$<$<CONFIG:RELEASE>:/Zi>")
    add_link_options("$<$<CONFIG:RELEASE>:/DEBUG>")
elseif(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    add_compile_options(-g)
endif()

set(CMAKE_MACOSX_RPATH ON)
list(APPEND CMAKE_INSTALL_RPATH $ENV{CONDA_PREFIX}/lib)

# Ensure that conda-installed libraries take precedence over
# system installed libraries.
list(APPEND CMAKE_PREFIX_PATH "$ENV{CONDA_PREFIX}")
list(APPEND CMAKE_PREFIX_PATH "$ENV{CONDA_PREFIX}/Library")

add_subdirectory(catkit2)
