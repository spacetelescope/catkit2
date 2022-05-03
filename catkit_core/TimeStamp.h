#ifndef TIMESTAMP_H
#define TIMESTAMP_H

#include <chrono>
#include <string>

uint64_t GetTimeStamp();
std::string ConvertTimestampToString(uint64_t timestamp);

class Timer
{
public:
	Timer();

	double GetTime();

private:
	std::chrono::steady_clock::time_point m_StartTime;
};

#endif // TIMESTAMP_H
