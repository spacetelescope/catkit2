#include "Event.h"
#include "Timing.h"
#include "LocalMemory.h"

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

#ifdef _WIN32
#include <windows.h>
#else
#include <pthread.h>
#endif

const size_t NUM_ITERATIONS = 100000;

void SetThreadAffinity(int core_id)
{
#ifdef _WIN32
	DWORD_PTR mask = 1ULL << core_id;
	SetThreadAffinityMask(GetCurrentThread(), mask);
#elif __linux__
	cpu_set_t cpuset;
	CPU_ZERO(&cpuset);
	CPU_SET(core_id, &cpuset);
	pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), &cpuset);
#else
	// MacOS and other platforms may not support thread affinity in the same way.
	std::cerr << "Thread affinity is not supported on this platform." << std::endl;
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
std::shared_ptr<Memory> buffer = nullptr;
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

		event->Signal();
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

		// Wait for the event to be signaled.
		event->Wait(2, []()
		{
			return !ready;
		}, method);

		auto timestamp_end = GetTimeStamp();
		latencies[i] = double(timestamp_end) - double(timestamp_start.load(std::memory_order_relaxed));
	}

	double sum = std::accumulate(latencies.begin(), latencies.end(), 0.0);
	double mean = sum / latencies.size();

	double sq_sum = std::inner_product(latencies.begin(), latencies.end(), latencies.begin(), 0.0);
	double stdev = std::sqrt(sq_sum / latencies.size() - mean * mean);

	std::cout << mean;
}

void print_usage()
{
	std::cerr << "Usage: event_latency (default | condition_variable | semaphore | futex | spinlock)" << std::endl;
}

int main(int argc, char *argv[])
{
	// Parse argument.
	if (argc < 2)
	{
		print_usage();
		return 1;
	}

	std::string wait_method_str = argv[1];
	EventWaitMethod wait_method;
	if (wait_method_str == "default")
	{
		wait_method = EventWaitMethod::Default;
	}
	else if (wait_method_str == "condition_variable")
	{
		wait_method = EventWaitMethod::ConditionVariable;
	}
	else if (wait_method_str == "semaphore")
	{
		wait_method = EventWaitMethod::Semaphore;
	}
	else if (wait_method_str == "futex")
	{
		wait_method = EventWaitMethod::Futex;
	}
	else if (wait_method_str == "spinlock")
	{
		wait_method = EventWaitMethod::SpinLock;
	}
	else
	{
		print_usage();
		return 2;
	}

	// Create the buffer.
	buffer = LocalMemory::Create(1024 * 1024);

	std::size_t num_cores = std::thread::hardware_concurrency();

	for (std::size_t i = 0; i < num_cores; ++i)
	{
		for (std::size_t j = 0; j < num_cores; ++j)
		{
			ready = false;

			auto receive_thread = std::thread(receive, j, wait_method);

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

	return 0;
}
