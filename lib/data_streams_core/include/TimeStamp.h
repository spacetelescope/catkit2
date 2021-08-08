#ifndef TIMESTAMP_H
#define TIMESTAMP_H

#include <chrono>
#include <string>

uint64_t GetTimeStamp();
std::string ConvertTimestampToString(uint64_t timestamp);

class TimeDelta
{
public:
	TimeDelta();

	double GetTimeDelta();

private:
	std::chrono::steady_clock::time_point m_LastTime;
};

#endif // TIMESTAMP_H