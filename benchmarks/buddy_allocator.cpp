#include "BuddyAllocator.h"
#include "Timing.h"
#include "LocalMemory.h"

#include <iostream>

void benchmark_linux_scalability()
{
	const size_t N = 10000000;
	const size_t BLOCK_SIZE = 32;
	const size_t MAX_SIZE = BLOCK_SIZE * (1 << 25);

	auto *handles = new BuddyAllocator::Handle[N];

	size_t buffer_size = BuddyAllocator::GetSharedStateSize(MAX_SIZE, BLOCK_SIZE);
	auto buffer = LocalMemory::Create(buffer_size);

	auto stream = StructStream(buffer);
	auto allocator = BuddyAllocator::Create(stream, MAX_SIZE, BLOCK_SIZE);

	auto start = GetTimeStamp();

	for (size_t i = 0; i < N; ++i)
	{
		handles[i] = allocator->Allocate(16);
	}

	for (size_t i = 0; i < N; ++i)
	{
		allocator->Release(handles[i]);
	}

	auto end = GetTimeStamp();

	std::cout << "Linux Scalability:" << std::endl;
	std::cout << "Time: " << (end - start) / 1e9 << " sec" << std::endl;
	std::cout << "Throughput: " << 2 * N / ((end - start) / 1e9) << " ops/s" << std::endl;
    std::cout << "Time per operation: " << (end - start) / (2 * N) << " ns" << std::endl;

	delete[] handles;
	delete[] buffer;
}

void benchmark_threadtest()
{
	const size_t N = 100;
	const size_t M = 100000;
	const size_t BLOCK_SIZE = 32;
	const size_t DEPTH = 24;
	const size_t MAX_SIZE = BLOCK_SIZE * (1 << DEPTH);

	auto *handles = new BuddyAllocator::Handle[M];

	size_t buffer_size = BuddyAllocator::GetSharedStateSize(MAX_SIZE, BLOCK_SIZE);
	auto buffer = LocalMemory::Create(buffer_size);

	auto stream = StructStream(buffer);
	auto allocator = BuddyAllocator::Create(stream, MAX_SIZE, BLOCK_SIZE);

	auto start = GetTimeStamp();

	for (size_t i = 0; i < M; ++i)
	{
		for (size_t j = 0; j < N; ++j)
		{
			handles[j] = allocator->Allocate(16);
		}

		for (size_t j = 0; j < N; ++j)
		{
			allocator->Release(handles[j]);
		}
	}

	auto end = GetTimeStamp();

	std::cout << "Threadtest:" << std::endl;
	std::cout << "Time: " << (end - start) / 1e9 << " sec" << std::endl;
	std::cout << "Throughput: " << 2 * N * M / ((end - start) / 1e9) << " ops/s" << std::endl;
    std::cout << "Time per operation: " << (end - start) / (2 * N * M) << " ns" << std::endl;

	delete[] handles;
}

void benchmark_larson()
{
	const size_t ALIGNMENT = 32;

	const size_t N = 10000000;
	const size_t M = 1000;
	const size_t MIN_SIZE = 1;
	const size_t MAX_SIZE = 16;
	const size_t BLOCK_SIZE = 16;
	const size_t DEPTH = 20;
	const size_t SIZE = BLOCK_SIZE * (1 << DEPTH);

	auto *handles = new BuddyAllocator::Handle[M];
	for (size_t i = 0; i < M; ++i)
		handles[i] = BuddyAllocator::INVALID_HANDLE;

	size_t buffer_size = BuddyAllocator::GetSharedStateSize(SIZE, BLOCK_SIZE);
	auto buffer = LocalMemory::Create(buffer_size);

	auto stream = StructStream(buffer);
	auto allocator = BuddyAllocator::Create(stream, SIZE, BLOCK_SIZE);

	auto *indices = new size_t[N];
	auto *sizes = new size_t[N];
	for (size_t i = 0; i < N; ++i)
	{
		indices[i] = rand() % M;
		sizes[i] = (MIN_SIZE + (rand() % (MAX_SIZE - MIN_SIZE))) * BLOCK_SIZE;
	}

	auto start = GetTimeStamp();

	for (size_t i = 0; i < N; ++i)
	{
		size_t index = indices[i];
		size_t size = sizes[i];

		if (handles[index] != BuddyAllocator::INVALID_HANDLE)
		{
			allocator->Release(handles[index]);
		}

		handles[index] = allocator->Allocate(size);
	}

	auto end = GetTimeStamp();
	std::cout << "Larson benchmark:" << std::endl;
	std::cout << "Time: " << (end - start) / 1e9 << " sec" << std::endl;
	std::cout << "Throughput: " << (N * 2 - M) / ((end - start) / 1e9) << " ops/s" << std::endl;
    std::cout << "Time per operation: " << (end - start) / (2 * N - M) << " ns" << std::endl;

	delete[] handles;
}

int main(int argc, char **argv)
{
	benchmark_linux_scalability();
	benchmark_threadtest();
	benchmark_larson();

	return 0;
}
