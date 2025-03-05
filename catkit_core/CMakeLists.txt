cmake_minimum_required(VERSION 3.5)

project(catkit_core)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

if(${CMAKE_SOURCE_DIR} STREQUAL ${CMAKE_BINARY_DIR})
  message(FATAL_ERROR "In-source builds not allowed. Please make a new directory (called a build directory) and run CMake from there. You may need to remove CMakeCache.txt.")
endif()

add_compile_options($<$<CXX_COMPILER_ID:MSVC>:/MP1>)

file(GLOB_RECURSE SOURCES "*.cpp")
file(GLOB_RECURSE HEADERS "*.h")

add_library(catkit_core STATIC "${SOURCES}")

set_property(TARGET catkit_core PROPERTY POSITION_INDEPENDENT_CODE ON)
target_compile_definitions(catkit_core PUBLIC PROTOBUF_USE_DLLS)

if (MSVC)
  # disable warning: 'identifier': class 'type' needs to have dll-interface to be used by clients of class 'type2'
  target_compile_options(catkit_core PUBLIC /wd4251)
endif()

# Link ZeroMQ
find_package(ZeroMQ REQUIRED)
target_include_directories(catkit_core PUBLIC ${ZeroMQ_INCLUDE_DIR})
target_link_libraries(catkit_core PUBLIC libzmq)
if (WIN32)
  target_link_libraries(catkit_core PUBLIC wsock32 ws2_32 Iphlpapi)
else()
  target_link_libraries(catkit_core PUBLIC pthread)
  if (NOT APPLE)
    target_link_libraries(catkit_core PUBLIC rt)
  endif (NOT APPLE)
endif (WIN32)

# Add includes for cppzmq
find_package(cppzmq REQUIRED)
target_include_directories(catkit_core PUBLIC ${CPPZMQ_INCLUDE_DIR})

# Link Eigen
find_package(Eigen3 REQUIRED NO_MODULE)
target_link_libraries (catkit_core PUBLIC Eigen3::Eigen)

# Link nlohmann JSON
find_package(nlohmann_json)
target_include_directories(catkit_core PRIVATE ${JSON_INCLUDE_DIR})

# Link protobuf
INCLUDE(FindProtobuf)
find_package(Protobuf REQUIRED)
target_include_directories(catkit_core PUBLIC ${PROTOBUF_INCLUDE_DIR})
target_link_libraries(catkit_core PUBLIC ${PROTOBUF_LIBRARY})

set(PROTO_BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}/gen/")
file(MAKE_DIRECTORY "${PROTO_BINARY_DIR}")
protobuf_generate(
  TARGET catkit_core
  IMPORT_DIRS ../proto
  PROTOC_OUT_DIR "${PROTO_BINARY_DIR}"
  PROTOS
    ../proto/core.proto
    ../proto/logging.proto
    ../proto/service.proto
    ../proto/testbed.proto
    ../proto/tracing.proto
)
target_include_directories(catkit_core PUBLIC "$<BUILD_INTERFACE:${PROTO_BINARY_DIR}>")
# Generate and install CatkitCoreConfig.cmake
include(CMakePackageConfigHelpers)

configure_package_config_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/CatkitCoreConfig.cmake.in"
  "${CMAKE_CURRENT_BINARY_DIR}/CatkitCoreConfig.cmake"
  INSTALL_DESTINATION lib/cmake/catkit_core
)

install(FILES
  "${CMAKE_CURRENT_BINARY_DIR}/CatkitCoreConfig.cmake"
  DESTINATION "${SKBUILD_PLATLIB_DIR}/cmake/catkit_core"
)

install(
  TARGETS catkit_core
  EXPORT CatkitCoreTargets
  LIBRARY DESTINATION lib
)

# Generate and install CatkitCoreTargets.cmake
install(
  EXPORT CatkitCoreTargets
  FILE CatkitCoreTargets.cmake
  DESTINATION "${SKBUILD_PLATLIB_DIR}/cmake/catkit_core"
)

install(DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
        DESTINATION "${SKBUILD_HEADERS_DIR}"
        FILES_MATCHING
        PATTERN "*.h"
        PATTERN "*.inl"
)
install(DIRECTORY "${PROTO_BINARY_DIR}"
        DESTINATION "${SKBUILD_HEADERS_DIR}/catkit_core"
        FILES_MATCHING
        PATTERN "*.h"
)
