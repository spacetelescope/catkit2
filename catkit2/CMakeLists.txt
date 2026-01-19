cmake_minimum_required(VERSION 3.21)

project(catkit_bindings)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED on)

set(SOURCES "bindings.cpp")

find_package(pybind11 REQUIRED)
pybind11_add_module(catkit_bindings ${SOURCES})

find_package(pybind11_json REQUIRED)
find_package(nlohmann_json REQUIRED)

target_include_directories(catkit_bindings PUBLIC ${CMAKE_SOURCE_DIR}/catkit2-core/src)

target_link_libraries(catkit_bindings PUBLIC nlohmann_json::nlohmann_json catkit2_core)

# Compile protobuf files.
find_package(Protobuf REQUIRED)

set(IMPORT_DIRS ${CMAKE_SOURCE_DIR}/catkit2-core/proto)
set(PROTO_FILES
    ${IMPORT_DIRS}/core.proto
    ${IMPORT_DIRS}/logging.proto
    ${IMPORT_DIRS}/service.proto
    ${IMPORT_DIRS}/testbed.proto
    ${IMPORT_DIRS}/tracing.proto
)

set(PYTHON_OUT_DIR ${CMAKE_CURRENT_SOURCE_DIR}/./proto/)

add_custom_target(
    catkit2_python_protobuf ALL
    COMMAND ${Protobuf_PROTOC_EXECUTABLE}
    --proto_path=${CMAKE_SOURCE_DIR}/catkit2-core/proto/
    --python_out=${PYTHON_OUT_DIR}
    ${PROTO_FILES}
    DEPENDS ${PROTO_FILES}
)

install(TARGETS catkit_bindings LIBRARY DESTINATION "${SKBUILD_PLATLIB_DIR}/catkit2/")
