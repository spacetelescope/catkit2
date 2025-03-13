#include "RingBuffer.h"
#include "Timing.h"
#include <iostream>

void benchmark_linux_scalability()
{
	const size_t N = 16;
    const size_t value_size = sizeof(size_t);

    char *buffer = new char[RingBuffer::CalculateMetadataBufferSize(N, value_size)];

    auto stream = StructStream(buffer);
	auto ring_buffer = RingBuffer::Create(stream, N, value_size);

    auto start = GetTimeStamp();

    for (size_t i = 0; i < N; ++i)
    {
        ring_buffer->Push(&i);

        std::size_t j;
        ring_buffer->Pop(&j);

        if (i != j)
        {
            std::cerr << "Error: " << i << " != " << j << std::endl;
        }
    }

	auto end = GetTimeStamp();

	std::cout << "Time: " << (end - start) / 1e9 << " sec" << std::endl;
	std::cout << "Throughput: " << 2 * N / ((end - start) / 1e9) << " ops/s" << std::endl;
    std::cout << "Time per operation: " << (end - start) / (2 * N) << " ns" << std::endl;

    delete[] buffer;
}

int main(int argc, char **argv)
{
	benchmark_linux_scalability();

	return 0;
}
