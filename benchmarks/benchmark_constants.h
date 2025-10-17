#ifndef BENCHMARK_CONSTANTS_H
#define BENCHMARK_CONSTANTS_H

#include <cstddef>

/**
 * @file BenchmarkConstants.h
 * @brief Shared constants for benchmarks and tests.
 *
 * This file centralizes common constants used across multiple benchmark
 * and test files to avoid code duplication and ensure consistency.
 */

/// Memory size conversions
constexpr size_t KILOBYTE = 1024;
constexpr size_t MEGABYTE = 1024 * 1024;
constexpr size_t GIGABYTE = 1024 * 1024 * 1024;

/// Common buffer sizes for benchmarks
constexpr size_t SMALL_BUFFER_SIZE = 32 * MEGABYTE;    ///< 32 MB for simple tests
constexpr size_t MEDIUM_BUFFER_SIZE = 128 * MEGABYTE;  ///< 128 MB for typical benchmarks
constexpr size_t LARGE_BUFFER_SIZE = 512 * MEGABYTE;   ///< 512 MB for stress tests
constexpr size_t XLARGE_BUFFER_SIZE = 2 * GIGABYTE;    ///< 2 GB for large-scale tests

#endif // BENCHMARK_CONSTANTS_H
