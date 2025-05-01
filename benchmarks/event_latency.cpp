#include "Event.h"
#include "Timing.h"

#include <thread>
#include <atomic>
#include <stdexcept>
#include <iostream>
#include <chrono>
#include <cstdint>
#include <cstddef>
#include <vector>
#include <numeric>
#include <cmath>

#include <windows.h>

const size_t NUM_ITERATIONS = 100000;

void SetThreadAffinity(int core_id)
{
#ifdef _WIN32
	DWORD_PTR mask = 1ULL << core_id;
	SetThreadAffinityMask(GetCurrentThread(), mask);
#else
	cpu_set_t cpuset;
	CPU_ZERO(&cpuset);
	CPU_SET(core_id, &cpuset);
	pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), &cpuset);
#endif
}

void fast_sleep(std::uint64_t ns)
{
	auto start = GetTimeStamp();

	while (GetTimeStamp() - start < ns)
	{
	}
}

std::atomic_bool ready = false;
char *buffer = nullptr;
std::atomic_uint64_t timestamp_start(0);

void submit(size_t core_id)
{
	SetThreadAffinity(core_id);

	// Create the event.
	auto stream = StructStream(buffer);
	auto event = Event::Open(stream);

	for (size_t i = 0; i < NUM_ITERATIONS; ++i)
	{
		while (!ready)
		{
			std::this_thread::yield();
		}

		ready = false;

		fast_sleep(1000);

		auto timestamp = GetTimeStamp();
		timestamp_start.store(timestamp, std::memory_order_relaxed);

		{
			EventLockGuard lock(event);
			event->Signal();
		}
	}
}

void receive(size_t core_id, EventWaitMethod method)
{
	SetThreadAffinity(core_id);

	// Open the event.
	auto stream = StructStream(buffer);
	auto event = Event::Create(stream, "test_event");

	std::vector<double> latencies(NUM_ITERATIONS);

	for (std::size_t i = 0; i < NUM_ITERATIONS; ++i)
	{
		ready = true;

		{
			EventLockGuard lock(event);

			// Wait for the event to be signaled.
			event->Wait(2, []() {
				return !ready;
			}, method);
		}

		auto timestamp_end = GetTimeStamp();
		latencies[i] = double(timestamp_end) - double(timestamp_start.load(std::memory_order_relaxed));
	}

	double sum = std::accumulate(latencies.begin(), latencies.end(), 0.0);
	double mean = sum / latencies.size();

	double sq_sum = std::inner_product(latencies.begin(), latencies.end(), latencies.begin(), 0.0);
	double stdev = std::sqrt(sq_sum / latencies.size() - mean * mean);

	std::cout << mean;
}
}

void main()
{
	std::cout << "Event latency benchmark." << std::endl;

	// Create the buffer.
	buffer = new char[1024 * 1024];

	std::size_t num_cores = std::thread::hardware_concurrency();
	std::cout << "Number of cores: " << num_cores << std::endl;

	for (auto method : {EventWaitMethod::Default, EventWaitMethod::SpinLock})
	{
		std::cout << "Method: " << static_cast<int>(method) << std::endl;

		for (std::size_t i = 0; i < num_cores; ++i)
		{
			for (std::size_t j = 0; j < num_cores; ++j)
			{
				ready = false;

				auto receive_thread = std::thread(receive, j, method);

				// Make sure the receive thread is ready before starting the submit thread.
				while (!ready)
				{
					std::this_thread::yield();
				}

				auto submit_thread = std::thread(submit, i);

				submit_thread.join();
				receive_thread.join();

			if (j != num_cores - 1)
			{
				std::cout << ", ";
			}
			else
			{
				std::cout << std::endl;
			}
		}
	}

	delete[] buffer;
}
