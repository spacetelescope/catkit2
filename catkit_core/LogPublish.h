#ifndef LOGPUBLISH_H
#define LOGPUBLISH_H

#include <zmq.hpp>

#include <string>
#include <queue>
#include <mutex>
#include <atomic>
#include <condition_variable>
#include <thread>

#include "Log.h"

class LogPublish : LogListener
{
public:
	LogPublish(std::string service_name, std::string host);
	~LogPublish();

    void AddLogEntry(const LogEntry &entry);

private:
	void MessageLoop();
	void ShutDown();

	std::thread m_MessageLoopThread;
	std::atomic_bool m_ShutDown;

	std::queue<std::string> m_LogMessages;
	std::mutex m_Mutex;
	std::condition_variable m_ConditionVariable;

	std::string m_ServiceName;
	std::string m_Host;
};

#endif // LOGPUBLISH_H
