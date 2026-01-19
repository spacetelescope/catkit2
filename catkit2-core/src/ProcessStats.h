#ifndef PROCESS_STATS_H
#define PROCESS_STATS_H

#include <cstdint>

class ProcessStats
{
public:
	ProcessStats();

	void Update();

	double GetCpuUsage() const;
	uint64_t GetMemoryUsage() const;

private:
	double m_CpuUsage = 0.0;
	uint64_t m_MemoryUsage = 0;

#if defined(_WIN32)
	void *m_ProcessHandle;

	unsigned long long m_LastProcTime = 0;
	unsigned long long m_LastSysTime = 0;
#elif defined(__APPLE__)
	uint64_t m_LastTotalTime = 0;
	uint64_t m_LastTaskTime = 0;
#else
	long m_LastProcJiffies = 0;
	long m_LastSysJiffies = 0;
#endif
};

#endif // PROCESS_STATS_H
