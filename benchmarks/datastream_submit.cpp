#include <iostream>
#include <string>
#include <vector>

#include "DataStream.h"
#include "Timing.h"

const size_t NUM_ITERATIONS = 10000;
const size_t NUM_FRAMES_IN_BUFFER = 20;

void benchmark(size_t N, bool with_data)
{
	auto stream_name = std::to_string(GetTimeStamp());
	auto stream = DataStream::Create(stream_name, "benchmark", DataType::DT_FLOAT64, {N, N}, NUM_FRAMES_IN_BUFFER);

	unsigned char *data = new unsigned char[N*N];

	auto start = GetTimeStamp();

	for (size_t j = 0; j < NUM_ITERATIONS; ++j)
	{
		if (with_data)
		{
			stream->SubmitData(data);
		}
		else
		{
			auto frame = stream->RequestNewFrame();
			stream->SubmitFrame(frame.m_Id);
		}
	}

	auto end = GetTimeStamp();
	auto time_per_iteration = double(end - start) / NUM_ITERATIONS;

	delete[] data;

	std::cout << N << "x" << N << ": " << time_per_iteration << " ns per submit" << std::endl;
}

int main(int argc, char *argv[])
{
	std::vector<size_t> Ns = {1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048};

	for (auto &with_data : {true, false})
	{
		std::cout << (with_data ? "With" : "Without") << " copying data:" << std::endl;

		for (auto &N : Ns)
		{
			benchmark(N, with_data);
		}
	}

	return 0;
}
