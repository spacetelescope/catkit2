#include "TimeStamp.h"

#include <sstream>
#include <iomanip>

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
	auto tp = system_clock::to_time_t(system_clock::time_point(time_since));

	stringstream ss("UTC ");
	ss << tp;

	return ss.str();
}

TimeDelta::TimeDelta()
{
	m_LastTime = steady_clock::now();
}

double TimeDelta::GetTimeDelta()
{
	auto now = steady_clock::now();
	double sec = duration_cast<duration<double>>(now - m_LastTime).count();

	m_LastTime = now;
	return sec;
}