#ifndef LOGFORWARDER_H
#define LOGFORWARDER_H

#include <zmq.hpp>

#include <string>
#include <queue>
#include <mutex>
#include <atomic>
#include <condition_variable>
#include <thread>

#include "Log.h"

class LogForwarder : LogListener
{
public:
	LogForwarder(std::string service_id, std::string host);
	~LogForwarder();

    void AddLogEntry(const LogEntry &entry);

private:
	void MessageLoop();
	void ShutDown();

	std::thread m_MessageLoopThread;
	std::atomic_bool m_ShutDown;

	std::queue<std::string> m_LogMessages;
	std::mutex m_Mutex;
	std::condition_variable m_ConditionVariable;

	std::string m_ServiceId;
	std::string m_Host;
};

#endif // LOGFORWARDER_H
