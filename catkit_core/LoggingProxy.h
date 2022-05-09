#ifndef LOGGING_PROXY_H
#define LOGGING_PROXY_H

#include "Log.h"
#include "TestbedProxy.h"

class LoggingProxy
{
public:
	LoggingProxy(std::shared_ptr<TestbedProxy> testbed);

	LogEntry GetNextEntry(double wait_time_in_seconds);

private:
	std::string m_Host;
	int m_Port;
};

#endif // LOGGING_PROXY_H
