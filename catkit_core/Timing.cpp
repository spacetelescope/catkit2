#include "Timing.h"

#include <sstream>
#include <iomanip>
#include <sstream>
#include <cstdint>
#include <ctime>

#if defined(__linux)
	#ifdef CLOCK_MONOTONIC
		#define CLOCKID CLOCK_MONOTONIC
	#else
		#define CLOCKID CLOCK_REALTIME
	#endif
#elif defined(__APPLE__)
	#include <mach/mach_time.h>
#elif defined(_WIN32)
	#define WIN32_LEAN_AND_MEAN
	#include <windows.h>
#endif

using namespace std;
using namespace std::chrono;

inline uint64_t compute_fraction(uint64_t x, uint64_t n, uint64_t d)
{
	// Compute x * n / d without overflowing.
	const uint64_t q = x / d;
	const uint64_t r = x % d;

	return q * n + r * n / d;
}

uint64_t ns()
{
	static bool is_initialized = 0;

#if defined(__APPLE__)
	static mach_timebase_info_data_t info;

	if (!is_initialized)
	{
		mach_timebase_info(&info);
		is_initialized = true;
	}

	uint64_t now;

	now = compute_fraction(mach_absolute_time(), info.numer, info.denom);

	return now;
#elif defined(__linux)
	static struct timespec linux_rate;

	if (!is_initialized)
	{
	  clock_getres(CLOCKID, &linux_rate);
	  is_initialized = true;
	}

	uint64_t now;

	struct timespec spec;
	clock_gettime(CLOCKID, &spec);
	now = uint64_t(spec.tv_sec) * 1000000000 + spec.tv_nsec;

	return now;
#elif defined(_WIN32)
	static LARGE_INTEGER win_frequency;

	if (!is_initialized)
	{
		QueryPerformanceFrequency(&win_frequency);
		is_initialized = true;
	}

	LARGE_INTEGER now;
	QueryPerformanceCounter(&now);

	return compute_fraction(now.QuadPart, 1000000000, win_frequency.QuadPart);
#else
	return duration_cast<system_clock::time_point::duration>(nanoseconds(timestamp));
#endif
}

uint64_t GetTimeStamp()
{
	// Perform correction of ns() to get the correct epoch.
	static auto before_ns = duration_cast<nanoseconds>(system_clock::now().time_since_epoch()).count();
	static auto epoch_of_ns = ns();
	static auto after_ns = duration_cast<nanoseconds>(system_clock::now().time_since_epoch()).count();

	static int64_t correction = int64_t(before_ns + after_ns) / 2 - int64_t(epoch_of_ns);

	return ns() + correction;
}

string ConvertTimestampToString(uint64_t timestamp)
{
	const auto time_since = duration_cast<system_clock::time_point::duration>(nanoseconds(timestamp));
	auto tp = system_clock::time_point(time_since);

	auto c = system_clock::to_time_t(tp);
	auto tm_local = *std::localtime(&c);

	std::stringstream ss;
	ss << std::put_time(&tm_local, "%F %T");
	ss << "." << std::setw(9) << std::setfill('0') << (timestamp % 1000000000) << " ";
	ss << std::put_time(&tm_local, "UTC%z");

	return ss.str();
}

Timer::Timer()
{
	m_StartTime = steady_clock::now();
}

double Timer::GetTime()
{
	auto now = steady_clock::now();

	return duration_cast<duration<double>>(now - m_StartTime).count();
}
