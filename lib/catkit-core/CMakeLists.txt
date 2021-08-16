cmake_minimum_required(VERSION 3.0)

project(core)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

add_library(catkit-core STATIC
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

target_include_directories(catkit-core PUBLIC "${CMAKE_CURRENT_LIST_DIR}/include")

# Use local version of ZeroMQ
set(ZeroMQ_LIBRARY ${CMAKE_CURRENT_LIST_DIR}/../../extern/zeromq-4.2.1/build/lib/Release/libzmq-v142-mt-4_2_1.lib)
set(ZeroMQ_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../../extern/zeromq-4.2.1/include)

# Link ZeroMQ
target_include_directories(catkit-core PUBLIC ${ZeroMQ_INCLUDE_DIR})
target_link_libraries(catkit-core PUBLIC ${ZeroMQ_LIBRARY})

# Add includes for cppzmq
set(CPPZMQ_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../../extern/cppzmq-4.7.1)
target_include_directories(catkit-core PUBLIC ${CPPZMQ_INCLUDE_DIR})

# Link Eigen
set(EIGEN_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../../extern/eigen-3.3.9)
target_include_directories(catkit-core PUBLIC ${EIGEN_INCLUDE_DIR})

# Link nlohmann JSON
set (JSON_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../../extern/json-3.9.1/include)
target_include_directories(catkit-core PUBLIC ${JSON_INCLUDE_DIR})
