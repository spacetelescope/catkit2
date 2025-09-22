cmake_minimum_required(VERSION 3.21)

project(catkit2_core)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED on)

if(${CMAKE_SOURCE_DIR} STREQUAL ${CMAKE_BINARY_DIR})
  message(FATAL_ERROR "In-source builds not allowed. Please make a new directory (called a build directory) and run CMake from there. You may need to remove CMakeCache.txt.")
endif()

add_compile_options($<$<CXX_COMPILER_ID:MSVC>:/MP1>)

file(GLOB_RECURSE SOURCES "./src/*.cpp")
file(GLOB_RECURSE HEADERS "./src/*.h")

add_library(catkit2_core STATIC)
target_sources(catkit2_core PRIVATE "${SOURCES}")
target_include_directories(
  catkit2_core
  INTERFACE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>
  $<INSTALL_INTERFACE:include>
)

set_property(TARGET catkit2_core PROPERTY POSITION_INDEPENDENT_CODE ON)
target_compile_definitions(catkit2_core PUBLIC PROTOBUF_USE_DLLS)

if (MSVC)
  # disable warning: 'identifier': class 'type' needs to have dll-interface to be used by clients of class 'type2'
  target_compile_options(catkit2_core PUBLIC /wd4251)
endif()

# Link ZeroMQ
find_package(ZeroMQ REQUIRED)
target_include_directories(catkit2_core PUBLIC ${ZeroMQ_INCLUDE_DIR})
target_link_libraries(catkit2_core PUBLIC libzmq)
if (WIN32)
  target_link_libraries(catkit2_core PUBLIC wsock32 ws2_32 Iphlpapi)
else()
  target_link_libraries(catkit2_core PUBLIC pthread)
  if (NOT APPLE)
    target_link_libraries(catkit2_core PUBLIC rt)
  endif (NOT APPLE)
endif (WIN32)

# Add includes for cppzmq
find_package(cppzmq REQUIRED)
target_include_directories(catkit2_core PUBLIC ${CPPZMQ_INCLUDE_DIR})

# Link Eigen
find_package(Eigen3 REQUIRED NO_MODULE)
target_link_libraries (catkit2_core PUBLIC Eigen3::Eigen)

# Link nlohmann JSON
find_package(nlohmann_json)
target_include_directories(catkit2_core PRIVATE ${JSON_INCLUDE_DIR})

# Link protobuf
INCLUDE(FindProtobuf)
find_package(Protobuf REQUIRED)
target_include_directories(catkit2_core PUBLIC ${PROTOBUF_INCLUDE_DIR})
target_link_libraries(catkit2_core PUBLIC ${PROTOBUF_LIBRARY})

set(PROTO_BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}/src/")
message("Proto binary dir: ${PROTO_BINARY_DIR}")
file(MAKE_DIRECTORY "${PROTO_BINARY_DIR}")
protobuf_generate(
  TARGET catkit2_core
  IMPORT_DIRS proto
  PROTOC_OUT_DIR "${PROTO_BINARY_DIR}"
  PROTOS
    proto/core.proto
    proto/logging.proto
    proto/service.proto
    proto/testbed.proto
    proto/tracing.proto
)
target_include_directories(catkit2_core PUBLIC "$<BUILD_INTERFACE:${PROTO_BINARY_DIR}>")
# Generate and install CatkitCoreConfig.cmake
include(CMakePackageConfigHelpers)

configure_package_config_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/CatkitCoreConfig.cmake.in"
  "${CMAKE_CURRENT_BINARY_DIR}/CatkitCoreConfig.cmake"
  INSTALL_DESTINATION lib/cmake/catkit2_core
)

install(FILES
  "${CMAKE_CURRENT_BINARY_DIR}/CatkitCoreConfig.cmake"
  DESTINATION "lib/cmake/catkit2_core"
)

install(
  TARGETS catkit2_core
  EXPORT CatkitCoreTargets
  LIBRARY DESTINATION lib
)

# Generate and install CatkitCoreTargets.cmake
install(
  EXPORT CatkitCoreTargets
  FILE CatkitCoreTargets.cmake
  DESTINATION "lib/cmake/catkit2_core"
)

install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/src/"
        DESTINATION include/catkit2_core
        FILES_MATCHING
        PATTERN "*.h"
        PATTERN "*.inl"
)
install(DIRECTORY "${PROTO_BINARY_DIR}"
        DESTINATION include/catkit2_core
        FILES_MATCHING
        PATTERN "*.h"
)
install(DIRECTORY "${PROTO_SOURCE_DIR}"
        DESTINATION include/catkit2_core/proto
        FILES_MATCHING
        PATTERN "*.proto"
)

add_subdirectory(benchmarks)
