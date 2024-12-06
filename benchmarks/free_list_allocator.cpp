#include "FreeListAllocator.h"
#include "Timing.h"
#include <iostream>

void benchmark_linux_scalability()
{
	typedef FreeListAllocator<16384, 32> Allocator;

	const size_t N = 10000000;

	auto *handles = new Allocator::BlockHandle[N];

	Allocator allocator(size_t(32) * N);

	auto start = GetTimeStamp();

	for (size_t i = 0; i < N; ++i)
	{
		handles[i] = allocator.Allocate(16);
	}

	for (size_t i = 0; i < N; ++i)
	{
		allocator.Deallocate(handles[i]);
	}

	auto end = GetTimeStamp();

	std::cout << "Linux Scalability:" << std::endl;
	std::cout << "Time: " << (end - start) / 1e9 << " sec" << std::endl;
	std::cout << "Throughput: " << 2 * N / ((end - start) / 1e9) << " ops/s" << std::endl;

	delete[] handles;
}

void benchmark_larson()
{
	const size_t ALIGNMENT = 32;
	typedef FreeListAllocator<16384, ALIGNMENT> Allocator;

	const size_t N = 10000000;
	const size_t M = 1000;
	const size_t MIN_SIZE = 16;
	const size_t MAX_SIZE = 128;

	auto *handles = new Allocator::BlockHandle[M];
	for (size_t i = 0; i < M; ++i)
	{
		handles[i] = -1;
	}

	auto *indices = new size_t[N];
	auto *sizes = new size_t[N];
	for (size_t i = 0; i < N; ++i)
	{
		indices[i] = rand() % M;
		sizes[i] = (MIN_SIZE + (rand() % (MAX_SIZE - MIN_SIZE))) * ALIGNMENT;
	}

	Allocator allocator(size_t(1024) * 1024 * 1024);

	auto start = GetTimeStamp();

	for (size_t i = 0; i < N; ++i)
	{
		size_t index = indices[i];
		size_t size = sizes[i];

		if (handles[index] != -1)
		{
			allocator.Deallocate(handles[index]);
		}

		handles[index] = allocator.Allocate(size);
	}

	auto end = GetTimeStamp();
	std::cout << "Larson benchmark:" << std::endl;
	std::cout << "Time: " << (end - start) / 1e9 << " sec" << std::endl;
	std::cout << "Throughput: " << (N * 2 - M) / ((end - start) / 1e9) << " ops/s" << std::endl;

	delete[] handles;
}

int main(int argc, char **argv)
{
	benchmark_linux_scalability();
	benchmark_larson();

	return 0;
}
