cmake_minimum_required(VERSION 3.0)

project(data_streams_core)

SET(CMAKE_CXX_FLAGS "-std=c++14")

add_library(data_streams_core STATIC DataStream.cpp TimeStamp.cpp)

target_include_directories(data_streams_core PUBLIC "${CMAKE_CURRENT_LIST_DIR}/include")
