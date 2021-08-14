cmake_minimum_required(VERSION 3.0)

project(data_streams_core)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

add_library(data_streams_core STATIC
    DataStream.cpp
    TimeStamp.cpp
    Log.cpp
    LogConsole.cpp
    LogFile.cpp)

target_include_directories(data_streams_core PUBLIC "${CMAKE_CURRENT_LIST_DIR}/include")

# Use local version of ZeroMQ
set(ZeroMQ_LIBRARY ${CMAKE_CURRENT_LIST_DIR}/../../extern/zeromq-4.2.1/build/lib/Release/libzmq-v142-mt-4_2_1.lib)
set(ZeroMQ_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../../extern/zeromq-4.2.1/build/include)

# Link ZeroMQ
target_include_directories(data_streams_core PUBLIC ${ZeroMQ_INCLUDE_DIR})
target_link_libraries(data_streams_core PUBLIC ${ZeroMQ_LIBRARY})

# Add includes for cppzmq
target_include_directories(data_streams_core PUBLIC ${CMAKE_CURRENT_LIST_DIR}/../../extern/cppzmq-4.7.1)
