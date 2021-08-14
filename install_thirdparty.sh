#!/bin/bash

mkdir extern
cd extern

# Install ZeroMQ
curl -L https://github.com/zeromq/libzmq/releases/download/v4.2.1/zeromq-4.2.1.tar.gz -O
tar xfz zeromq-4.2.1.tar.gz
rm -f zeromq-4.2.1.tar.gz
cd zeromq-4.2.1/
cmake -B "./build" -D ZMQ_BUILD_TESTS=OFF -D CMAKE_BUILD_TYPE=Release -D WITH_PERF_TOOL=OFF
cmake --build ./build --config Release
cd ..

# Install cppzmq
curl -L https://github.com/zeromq/cppzmq/archive/refs/tags/v4.7.1.tar.gz -O
tar xfz v4.7.1.tar.gz
rm -f v4.7.1.tar.gz

# Install pybind11
git clone https://github.com/pybind/pybind11

# Install Eigen
curl -L https://gitlab.com/libeigen/eigen/-/archive/3.3.9/eigen-3.3.9.tar.gz -O
tar xfs eigen-3.3.9.tar.gz
rm -f eigen-3.3.9.tar.gz

# Revert to original directory
cd ..
