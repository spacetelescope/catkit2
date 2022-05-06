#include "Util.h"

#ifdef _WIN32
	#define WIN32_LEAN_AND_MEAN
	#include <windows.h>
#else
	#include <unistd.h>
#endif // _WIN32

#include <thread>
#include <atomic>

#ifdef _WIN32
	int GetProcessId()
	{
		static int process_id(GetCurrentProcessId());
		return process_id;
	}
#else
	typedef pid_t ProcessId;

	int GetProcessId()
	{
		static int process_id(getpid());
		return process_id;
	}
#endif // _WIN32

int GetThreadId()
{
	static std::atomic_int next_thread_id(0);
	thread_local static int thread_id(next_thread_id++);

	return thread_id;
}
