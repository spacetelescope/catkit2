#include "PoolAllocator.h"
#include "Timing.h"
#include <iostream>

void benchmark_linux_scalability()
{
	typedef PoolAllocator<16384> Allocator;

	const size_t N = 10000000;

	auto *handles = new size_t[N];

	Allocator allocator;

	auto start = GetTimeStamp();

	for (size_t i = 0; i < N; ++i)
	{
		handles[i] = allocator.Allocate();
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

int main(int argc, char **argv)
{
	benchmark_linux_scalability();

	return 0;
}
