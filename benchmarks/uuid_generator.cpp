#include "UuidGenerator.h"
#include "Timing.h"

#include <iostream>

int main()
{
	const size_t N = 100000000;

	UuidGenerator generator;

	char uuid[16];

	std::cout << std::hex;

	auto start = GetTimeStamp();

	for (size_t i = 0; i < N; ++i)
	{
		generator.GenerateUuid(uuid);
	}

	auto end = GetTimeStamp();

	std::cout << std::dec;

	std::cout << "Time: " << (end - start) / 1e9 << " sec" << std::endl;
	std::cout << "Throughput: " << N / ((end - start) / 1e9) << " ops/s" << std::endl;
	std::cout << "Time per operation: " << (end - start) / N << " ns" << std::endl;

	return 0;
}
