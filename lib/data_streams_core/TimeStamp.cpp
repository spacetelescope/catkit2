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
	auto tp = system_clock::to_time_t(system_clock::time_point(nanoseconds(timestamp)));
	auto time = gmtime(&tp);

	stringstream ss("UTC ");
	ss << time->tm_year + 1900 << "/";
	ss << setfill('0') << setw(2);
	ss << time->tm_mon << "/" << time->tm_mday;
	ss << " ";
	ss << time->tm_hour << ":" << time->tm_min << ":" << time->tm_sec;
	ss << ".";
	ss << setfill('0') << setw(9);
	ss << (timestamp % 1000000000);

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