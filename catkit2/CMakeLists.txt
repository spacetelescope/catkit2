cmake_minimum_required(VERSION 3.21)

project(catkit_bindings)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED on)

set(SOURCES "bindings.cpp")

find_package(pybind11 REQUIRED)
pybind11_add_module(catkit_bindings ${SOURCES})

find_package(pybind11_json REQUIRED)
target_include_directories(catkit_bindings PUBLIC pybind11_json_INCLUDE_DIRS)

target_include_directories(catkit_bindings PUBLIC ../catkit_core)

target_link_libraries(catkit_bindings PUBLIC catkit_core)

# Compile protobuf files.
find_package(Protobuf REQUIRED)

set(PROTO_FILES
    ${CMAKE_CURRENT_SOURCE_DIR}/../proto/core.proto
    ${CMAKE_CURRENT_SOURCE_DIR}/../proto/logging.proto
    ${CMAKE_CURRENT_SOURCE_DIR}/../proto/service.proto
    ${CMAKE_CURRENT_SOURCE_DIR}/../proto/testbed.proto
    ${CMAKE_CURRENT_SOURCE_DIR}/../proto/tracing.proto
)

set(PYTHON_OUT_DIR ${CMAKE_CURRENT_SOURCE_DIR}/./proto/)

add_custom_target(
    catkit2_python_protobuf ALL
    COMMAND ${Protobuf_PROTOC_EXECUTABLE}
    --proto_path=${CMAKE_CURRENT_SOURCE_DIR}/../proto/
    --python_out=${PYTHON_OUT_DIR}
    ${PROTO_FILES}
    DEPENDS ${PROTO_FILES}
)

install(TARGETS catkit_bindings LIBRARY DESTINATION "${SKBUILD_PLATLIB_DIR}/catkit2/")
