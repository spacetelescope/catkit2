#!/bin/bash

# Install ZeroMQ
cd zeromq-4.2.1/
mkdir build
cd build
cmake .. -D ZMQ_BUILD_TESTS=OFF -D CMAKE_BUILD_TYPE=Release -D WITH_PERF_TOOL=OFF
cmake --build . --config Release
cd ../..

# Install cppzmq
cd cppzmq-4.7.1/
mkdir build
cd build
cmake .. -D CPPZMQ_BUILD_TESTS=OFF
cmake --build . --config Release
cd ../..
