#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <numeric>
#include <fstream>
#include <atomic>

#include "DataStream.h"
#include "Timing.h"

const size_t NUM_ITERATIONS = 1000000;

void sleep(std::uint64_t ns)
{
	auto start = GetTimeStamp();

	while (GetTimeStamp() - start < ns)
	{
	}
}

std::atomic_bool ready = false;

void submit(std::string stream_id)
{
	std::cout << "Running latency benchmark";

	auto stream = DataStream::Open(stream_id);

	for (size_t i = 0; i < NUM_ITERATIONS; ++i)
	{
		while (!ready)
		{
		}

		ready = false;

		sleep(1000);

		auto frame = stream->RequestNewFrame();
		stream->SubmitFrame(frame.m_Id);

		if (i % (NUM_ITERATIONS / 10) == 0)
		{
			std::cout << "." << std::flush;
		}
	}

	std::cout << std::endl;
}

void receive(std::string stream_id)
{
	auto stream = DataStream::Open(stream_id);

	std::vector<size_t> latencies(NUM_ITERATIONS);

	for (size_t i = 0; i < NUM_ITERATIONS; ++i)
	{
		ready = true;

		auto frame = stream->GetNextFrame(1000);
		auto time = GetTimeStamp();

		latencies[i] = time - frame.m_TimeStamp;
	}

	double sum = std::accumulate(latencies.begin(), latencies.end(), 0.0);
	double mean = sum / latencies.size();

	double sq_sum = std::inner_product(latencies.begin(), latencies.end(), latencies.begin(), 0.0);
	double stdev = std::sqrt(sq_sum / latencies.size() - mean * mean);

	std::cout << mean << " +/- " << stdev << " ns" << std::endl;

	// Write results to a file.
	std::ofstream file;
	file.open("results.txt");

	for (auto &latency : latencies)
	{
		file << latency << std::endl;
	}

	file.close();

	std::cout << "All latencies were written to results.txt." << std::endl;
}

int main(int argc, char *argv[])
{
	const size_t N = 16;
	const size_t NUM_FRAMES_IN_BUFFER = 20;

	auto stream_name = std::to_string(GetTimeStamp());
	auto stream = DataStream::Create(stream_name, "benchmark", DataType::DT_FLOAT64, {N, N}, NUM_FRAMES_IN_BUFFER);

	std::thread receive_thread(receive, stream->GetStreamId());

	// Make sure that the receive thread has started.
	std::this_thread::sleep_for(std::chrono::milliseconds(10));

	std::thread submit_thread(submit, stream->GetStreamId());

	submit_thread.join();
	receive_thread.join();

	return 0;
}
