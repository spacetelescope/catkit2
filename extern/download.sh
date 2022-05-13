#!/bin/bash

# Download cppzmq
curl -L https://github.com/zeromq/cppzmq/archive/refs/tags/v4.7.1.tar.gz -O
tar xfz v4.7.1.tar.gz
rm -f v4.7.1.tar.gz

# Download pybind11
git clone https://github.com/pybind/pybind11

# Download Eigen
curl -L https://gitlab.com/libeigen/eigen/-/archive/3.3.9/eigen-3.3.9.tar.gz -O
tar xfz eigen-3.3.9.tar.gz
rm -f eigen-3.3.9.tar.gz

# Download nlohmann JSON
curl -L https://github.com/nlohmann/json/archive/refs/tags/v3.9.1.tar.gz -O
tar xfz v3.9.1.tar.gz
rm -f v3.9.1.tar.gz

# Download pybind11 to JSON converter
curl -L https://github.com/pybind/pybind11_json/archive/refs/tags/0.2.11.tar.gz -O
tar xfz 0.2.11.tar.gz
rm -f 0.2.11.tar.gz
