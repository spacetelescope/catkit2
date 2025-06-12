#include "ProcessStats.h"

#include <iostream>
#include <thread>

#if defined(_WIN32)
	#include <windows.h>
	#include <psapi.h>
#elif defined(__APPLE__)
	#include <mach/mach.h>
	#include <mach/host_info.h>
	#include <mach/task_info.h>
#else  // Linux
	#include <fstream>
	#include <sstream>
	#include <unistd.h>
#endif

#if defined(_WIN32)

static ULONGLONG fileTimeToUInt64(const FILETIME& ft)
{
	ULARGE_INTEGER li;
	li.LowPart = ft.dwLowDateTime;
	li.HighPart = ft.dwHighDateTime;

	return li.QuadPart;
}

unsigned long long getProcessTime(void* handle)
{
	FILETIME createTime, exitTime, kernelTime, userTime;

	if (!GetProcessTimes((HANDLE)handle, &createTime, &exitTime, &kernelTime, &userTime))
		return 0;

	return fileTimeToUInt64(kernelTime) + fileTimeToUInt64(userTime);
}

unsigned long long getSystemTime()
{
	FILETIME idle, kernel, user;

	if (!GetSystemTimes(&idle, &kernel, &user))
		return 0;

	return fileTimeToUInt64(kernel) + fileTimeToUInt64(user);
}

#elif defined(__APPLE__)

uint64_t getTotalSystemTime()
{
	host_cpu_load_info_data_t cpuinfo;
	mach_msg_type_number_t count = HOST_CPU_LOAD_INFO_COUNT;
	if (host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO, (host_info_t)&cpuinfo, &count) != KERN_SUCCESS)
		return 0;

	return static_cast<uint64_t>(
		cpuinfo.cpu_ticks[CPU_STATE_USER] +
		cpuinfo.cpu_ticks[CPU_STATE_SYSTEM] +
		cpuinfo.cpu_ticks[CPU_STATE_IDLE] +
		cpuinfo.cpu_ticks[CPU_STATE_NICE]
	);
}

uint64_t getTaskTime()
{
	task_thread_times_info_data_t info;
	mach_msg_type_number_t count = TASK_THREAD_TIMES_INFO_COUNT;

	if (task_info(mach_task_self(), TASK_THREAD_TIMES_INFO, (task_info_t)&info, &count) != KERN_SUCCESS)
		return 0;

	uint64_t micros = (uint64_t)(info.user_time.seconds + info.system_time.seconds) * 1'000'000 +
		(info.user_time.microseconds + info.system_time.microseconds);

	return micros;
}

#else

long readProcessJiffies()
{
	std::ifstream stat("/proc/self/stat");

	if (!stat)
		return 0;

	std::string dummy;
	long utime = 0;
	long stime = 0;

	for (int i = 0; i < 13; ++i)
		stat >> dummy;

	stat >> utime >> stime;

	return utime + stime;
}

long readSystemJiffies()
{
	std::ifstream stat("/proc/stat");

	if (!stat)
		return 0;

	std::string label;

	long total = 0;
	long tmp;

	stat >> label;

	while (stat >> tmp)
		total += tmp;

	return total;
}

long readProcessRSS()
{
	std::ifstream stat("/proc/self/stat");

	if (!stat)
		return 0;

	std::string dummy;
	long rss = 0;

	for (int i = 0; i < 23; ++i)
		stat >> dummy;

	stat >> rss;

	return rss * sysconf(_SC_PAGE_SIZE);
}
#endif

ProcessStats::ProcessStats()
{
#if defined(_WIN32)
	m_ProcessHandle = GetCurrentProcess();
	m_LastProcTime = getProcessTime(m_ProcessHandle);
	m_LastSysTime = getSystemTime();
#elif defined(__APPLE__)
	m_LastTotalTime = getTotalSystemTime();
	m_LastTaskTime = getTaskTime();
#else
	m_LastProcJiffies = readProcessJiffies();
	m_LastSysJiffies = readSystemJiffies();
#endif
}

void ProcessStats::Update()
{
#if defined(_WIN32)
	auto current_proc_time = getProcessTime(m_ProcessHandle);
	auto current_sys_time = getSystemTime();

	if (current_sys_time > m_LastSysTime)
		m_CpuUsage = 100.0 * (current_proc_time - m_LastProcTime) / (current_sys_time - m_LastSysTime);

	m_LastProcTime = current_proc_time;
	m_LastSysTime = current_sys_time;

	PROCESS_MEMORY_COUNTERS pmc;
	if (GetProcessMemoryInfo(m_ProcessHandle, &pmc, sizeof(pmc)))
		m_MemoryUsage = pmc.WorkingSetSize;

#elif defined(__APPLE__)
	uint64_t current_total = getTotalSystemTime();
	uint64_t current_task = getTaskTime();

	if (current_total > m_LastTotalTime)
		m_CpuPercent = 100.0 * (current_task - m_LastTaskTime) / (current_total - m_LastTotalTime);

	m_LastTotalTime = current_total;
	m_LastTaskTime = current_task;

	task_basic_info_data_t info;
	mach_msg_type_number_t count = TASK_BASIC_INFO_COUNT;

	if (task_info(mach_task_self(), TASK_BASIC_INFO, (task_info_t) &info, &count) == KERN_SUCCESS)
		m_MemoryUsage = info.resident_size;

#else
	long current_proc = readProcessJiffies();
	long current_sys = readSystemJiffies();

	if (current_sys > m_LastSysJiffies)
	{
		int numCpus = sysconf(_SC_NPROCESSORS_ONLN);
		m_CpuPercent = 100.0 * (current_proc - m_LastProcJiffies) / (current_sys - m_LastSysJiffies) * numCpus;
	}

	m_LastProcJiffies = current_proc;
	m_LastSysJiffies = current_sys;

	m_MemoryUsage = readProcessRSS();
#endif
}

double ProcessStats::GetCpuUsage() const
{
	return m_CpuUsage;
}

uint64_t ProcessStats::GetMemoryUsage() const
{
	return m_MemoryUsage;
}
