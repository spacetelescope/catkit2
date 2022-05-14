cmake_minimum_required(VERSION 3.0)

project(catkit_core)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

if(${CMAKE_SOURCE_DIR} STREQUAL ${CMAKE_BINARY_DIR})
  message(FATAL_ERROR "In-source builds not allowed. Please make a new directory (called a build directory) and run CMake from there. You may need to remove CMakeCache.txt.")
endif()

add_compile_options($<$<CXX_COMPILER_ID:MSVC>:/MP1>)

add_library(catkit_core STATIC
    DataStream.cpp
    SharedMemory.cpp
    Synchronization.cpp
    TimeStamp.cpp
    Log.cpp
    LogConsole.cpp
    LogFile.cpp
    LogPublish.cpp
    HostName.cpp
    Command.cpp
    Property.cpp
    Service.cpp
    Communication.cpp
    TestbedProxy.cpp
    ServiceProxy.cpp
    ServiceState.cpp
    Tensor.cpp
    ../proto/gen/cpp/core.pb.cc
    ../proto/gen/cpp/logging.pb.cc
    ../proto/gen/cpp/testbed.pb.cc
    ../proto/gen/cpp/service.pb.cc
    ../proto/gen/cpp/tracing.pb.cc)

  target_include_directories(catkit_core PUBLIC ${CMAKE_CURRENT_LIST_DIR}/../proto/gen/cpp)

set_property(TARGET catkit_core PROPERTY POSITION_INDEPENDENT_CODE ON)

# Link ZeroMQ
find_package(ZeroMQ REQUIRED)
target_include_directories(catkit_core PUBLIC ${ZeroMQ_INCLUDE_DIR})
target_link_libraries(catkit_core PUBLIC libzmq)
if (WIN32)
  target_link_libraries(catkit_core PUBLIC wsock32 ws2_32 Iphlpapi)
else()
  target_link_libraries(catkit_core PUBLIC pthread)
endif (WIN32)

# Add includes for cppzmq
set(CPPZMQ_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../extern/cppzmq-4.8.1)
target_include_directories(catkit_core PUBLIC ${CPPZMQ_INCLUDE_DIR})

# Link Eigen
set(EIGEN_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../extern/eigen-3.3.9)
target_include_directories(catkit_core PUBLIC ${EIGEN_INCLUDE_DIR})

# Link nlohmann JSON
set (JSON_INCLUDE_DIR ${CMAKE_CURRENT_LIST_DIR}/../extern/json-3.9.1/include)
target_include_directories(catkit_core PUBLIC ${JSON_INCLUDE_DIR})

# Link protobuf
INCLUDE(FindProtobuf)
find_package(Protobuf REQUIRED)
target_include_directories(catkit_core PUBLIC ${PROTOBUF_INCLUDE_DIR})
target_link_libraries(catkit_core PUBLIC ${PROTOBUF_LIBRARY})

# Add install files
install(TARGETS catkit_core DESTINATION lib)
install(DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
        DESTINATION include
        FILES_MATCHING
        PATTERN "*.h"
        PATTERN "*.inl"
)
install(DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/../proto/gen/cpp/
        DESTINATION include/catkit_core
        FILES_MATCHING
        PATTERN "*.h"
)
