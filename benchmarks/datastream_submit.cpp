#include <iostream>
#include <string>
#include <vector>

#include "DataStream.h"
#include "Timing.h"

const size_t NUM_ITERATIONS = 10000;

void benchmark(bool with_data)

int main(int argc, char *argv[])
{
	std::vector<size_t> Ns = {1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048};

	for (auto &N : Ns)
	{
		const size_t NUM_FRAMES_IN_BUFFER = 20;

		auto stream_name = std::to_string(GetTimeStamp());
		auto stream = DataStream::Create(stream_name, "benchmark", DataType::DT_FLOAT64, {N, N}, NUM_FRAMES_IN_BUFFER);

		unsigned char *data = new unsigned char[N*N];

		auto start = GetTimeStamp();

		for (size_t j = 0; j < NUM_ITERATIONS; ++j)
		{
			stream->SubmitData(data);
		}

		auto end = GetTimeStamp();
		auto time_per_iteration = double(end - start) / NUM_ITERATIONS;

		delete[] data;

		std::cout << N << "x" << N << ": " << time_per_iteration << " ns per submit" << std::endl;
	}

	return 0;
}
