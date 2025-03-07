#include "PoolAllocator.h"
#include "Timing.h"
#include "StructStream.h"
#include <iostream>

void benchmark_linux_scalability()
{
	const size_t N = 10000000;
	const size_t CAPACITY = 2 * N;

	char *buffer = new char[PoolAllocator::GetMemorySize(CAPACITY)];
	auto stream = StructStream(buffer);

	auto allocator = PoolAllocator::Create(stream, CAPACITY);

	auto *handles = new PoolAllocator::BlockHandle[N];

	auto start = GetTimeStamp();

	for (size_t i = 0; i < N; ++i)
	{
		handles[i] = allocator->Allocate();
	}

	for (size_t i = 0; i < N; ++i)
	{
		allocator->Deallocate(handles[i]);
	}

	auto end = GetTimeStamp();

	std::cout << "Linux Scalability:" << std::endl;
	std::cout << "Time: " << (end - start) / 1e9 << " sec" << std::endl;
	std::cout << "Throughput: " << 2 * N / ((end - start) / 1e9) << " ops/s" << std::endl;
	std::cout << "Time per operation: " << (end - start) / (2 * N) << " ns" << std::endl;

	delete[] handles;
	delete[] buffer;
}

int main(int argc, char **argv)
{
	benchmark_linux_scalability();

	return 0;
}
