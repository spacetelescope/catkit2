cmake_minimum_required(VERSION 3.21)

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

# Pool allocator benchmark
add_executable(pool_allocator pool_allocator.cpp)
target_include_directories(pool_allocator PUBLIC ../catkit_core)
target_link_libraries(pool_allocator PUBLIC catkit_core)

# Hash map benchmark
add_executable(hash_map hash_map.cpp)
target_include_directories(hash_map PUBLIC ../catkit_core)
target_link_libraries(hash_map PUBLIC catkit_core)

# Uuid generator benchmark
add_executable(uuid_generator uuid_generator.cpp)
target_include_directories(uuid_generator PUBLIC ../catkit_core)
target_link_libraries(uuid_generator PUBLIC catkit_core)

# MessageBroker benchmark
add_executable(message_broker message_broker.cpp)
target_include_directories(message_broker PUBLIC ../catkit_core)
target_link_libraries(message_broker PUBLIC catkit_core)

# BuddyAllocator benchmark
add_executable(buddy_allocator buddy_allocator.cpp)
target_include_directories(buddy_allocator PUBLIC ../catkit_core)
target_link_libraries(buddy_allocator PUBLIC catkit_core)

# HybridPoolAllocator benchmark
add_executable(hybrid_pool_allocator hybrid_pool_allocator.cpp)
target_include_directories(hybrid_pool_allocator PUBLIC ../catkit_core)
target_link_libraries(hybrid_pool_allocator PUBLIC catkit_core)

# Event latency benchmark
add_executable(event_latency event_latency.cpp)
target_include_directories(event_latency PUBLIC ../catkit_core)
target_link_libraries(event_latency PUBLIC catkit_core)

# Add install files
install(TARGETS datastream_latency DESTINATION bin)
install(TARGETS datastream_submit DESTINATION bin)
install(TARGETS timestamp DESTINATION bin)
install(TARGETS pool_allocator DESTINATION bin)
install(TARGETS hash_map DESTINATION bin)
install(TARGETS uuid_generator DESTINATION bin)
install(TARGETS message_broker DESTINATION bin)
install(TARGETS buddy_allocator DESTINATION bin)
install(TARGETS hybrid_pool_allocator DESTINATION bin)
install(TARGETS event_latency DESTINATION bin)
