cmake_minimum_required(VERSION 3.0)

project(catkit2)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED on)

if(${CMAKE_SOURCE_DIR} STREQUAL ${CMAKE_BINARY_DIR})
  message(FATAL_ERROR "In-source builds not allowed. Please make a new directory (called a build directory) and run CMake from there. You may need to remove CMakeCache.txt.")
endif()

# DataStream latency benchmark
add_executable(datastream_latency datastream_latency.cpp)
target_include_directories(datastream_latency PUBLIC ../catkit_core)
target_link_libraries(datastream_latency PUBLIC catkit_core)

# Datastream submit benchmark
add_executable(datastream_submit datastream_submit.cpp)
target_include_directories(datastream_submit PUBLIC ../catkit_core)
target_link_libraries(datastream_submit PUBLIC catkit_core)

# Timestamp benchmark
add_executable(timestamp timestamp.cpp)
target_include_directories(timestamp PUBLIC ../catkit_core)
target_link_libraries(timestamp PUBLIC catkit_core)

# Add install files
install(TARGETS datastream_latency DESTINATION bin)
install(TARGETS datastream_submit DESTINATION bin)
install(TARGETS timestamp DESTINATION bin)
