cmake_minimum_required(VERSION 3.0)

project(data_streams_core)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

add_library(data_streams_core STATIC DataStream.cpp TimeStamp.cpp)

target_include_directories(data_streams_core PUBLIC "${CMAKE_CURRENT_LIST_DIR}/include")
