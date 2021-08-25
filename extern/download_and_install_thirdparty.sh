#!/bin/bash

# Install ZeroMQ
curl -L https://github.com/zeromq/libzmq/releases/download/v4.2.1/zeromq-4.2.1.tar.gz -O
tar xfz zeromq-4.2.1.tar.gz
rm -f zeromq-4.2.1.tar.gz
cd zeromq-4.2.1/
mkdir build
cd build
cmake .. -D ZMQ_BUILD_TESTS=OFF -D CMAKE_BUILD_TYPE=Release -D WITH_PERF_TOOL=OFF
cmake --build . --config Release
cd ../..

# Install cppzmq
curl -L https://github.com/zeromq/cppzmq/archive/refs/tags/v4.7.1.tar.gz -O
tar xfz v4.7.1.tar.gz
rm -f v4.7.1.tar.gz
cd cppzmq-4.7.1/
mkdir build
cd build
cmake .. -D CPPZMQ_BUILD_TESTS=OFF
cmake --build . --config Release
cd ../..

# Install pybind11
git clone https://github.com/pybind/pybind11

# Install Eigen
curl -L https://gitlab.com/libeigen/eigen/-/archive/3.3.9/eigen-3.3.9.tar.gz -O
tar xfz eigen-3.3.9.tar.gz
rm -f eigen-3.3.9.tar.gz

# Install nlohmann JSON
curl -L https://github.com/nlohmann/json/archive/refs/tags/v3.9.1.tar.gz -O
tar xfz v3.9.1.tar.gz
rm -f v3.9.1.tar.gz

# Install pybind11 to JSON converter
curl -L https://github.com/pybind/pybind11_json/archive/refs/tags/0.2.11.tar.gz -O
tar xfz 0.2.11.tar.gz
rm -f 0.2.11.tar.gz
