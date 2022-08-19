#include "Util.h"

#include "Time.h"

#ifdef _WIN32
	#define WIN32_LEAN_AND_MEAN
	#include <windows.h>
#else
	#include <unistd.h>
#endif // _WIN32

#include <thread>
#include <atomic>
#include <chrono>

int GetProcessId()
{
#ifdef _WIN32
	static int process_id(GetCurrentProcessId());
	return process_id;
#else
	static int process_id(getpid());
	return process_id;
#endif // _WIN32
}

int GetThreadId()
{
	static std::atomic_int next_thread_id(0);
	thread_local static int thread_id(next_thread_id++);

	return thread_id;
}

void Sleep(double sleep_time_in_sec, bool (*cancellation_callback)())
{
	Timer timer;

	while (true)
	{
		double sleep_remaining = sleep_time_in_sec - timer.GetTime();

		// Sleep is over when timer has expired.
		if (sleep_remaining < 0)
			break;

		// Sleep is over when cancellation is requested.
		if (cancellation_callback)
		{
			if (cancellation_callback())
				break;
		}

		std::this_thread::sleep_for(std::chrono::duration<double>(std::min(double(0.001)), sleep_remaining)));
	}
}
