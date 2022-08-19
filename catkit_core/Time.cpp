#include "Time.h"

#include <sstream>
#include <iomanip>
#include <sstream>

using namespace std;
using namespace std::chrono;

uint64_t GetTimeStamp()
{
	auto time_since_epoch = system_clock::now().time_since_epoch();
	return duration_cast<nanoseconds>(time_since_epoch).count();
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
