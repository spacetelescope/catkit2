cmake_minimum_required(VERSION 3.0)

project(hicat_core)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

if(${CMAKE_SOURCE_DIR} STREQUAL ${CMAKE_BINARY_DIR})
  message(FATAL_ERROR "In-source builds not allowed. Please make a new directory (called a build directory) and run CMake from there. You may need to remove CMakeCache.txt.")
endif()

add_compile_options($<$<CXX_COMPILER_ID:MSVC>:/MP1>)

add_library(hicat_core STATIC
    DataStream.cpp
    TimeStamp.cpp
    Log.cpp
    LogConsole.cpp
    LogFile.cpp
    Serialization.cpp
    HostName.cpp
    Command.cpp
    Property.cpp
    Module.cpp)

target_include_directories(hicat_core PUBLIC "${CMAKE_CURRENT_LIST_DIR}/include")

# Use local version of ZeroMQ
set(ZeroMQ_LIBRARY ${CMAKE_CURRENT_LIST_DIR}/../extern/zeromq-4.2.1/build/lib/Release/libzmq-static-v142-mt-s-4_2_1.lib)
set(ZeroMQ_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../extern/zeromq-4.2.1/include)

add_definitions(-DZMQ_STATIC)

# Link ZeroMQ
target_include_directories(hicat_core PUBLIC ${ZeroMQ_INCLUDE_DIR})
target_link_libraries(hicat_core PUBLIC ${ZeroMQ_LIBRARY})
target_link_libraries(hicat_core PUBLIC wsock32 ws2_32 Iphlpapi)

# Add includes for cppzmq
set(CPPZMQ_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../extern/cppzmq-4.7.1)
target_include_directories(hicat_core PUBLIC ${CPPZMQ_INCLUDE_DIR})

# Link Eigen
set(EIGEN_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../extern/eigen-3.3.9)
target_include_directories(hicat_core PUBLIC ${EIGEN_INCLUDE_DIR})

# Link nlohmann JSON
set (JSON_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../extern/json-3.9.1/include)
target_include_directories(hicat_core PUBLIC ${JSON_INCLUDE_DIR})
