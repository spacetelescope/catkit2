#ifndef LOGPUBLISH_H
#define LOGPUBLISH_H

#include <zmq.hpp>

#include <string>

#include "Log.h"

class LogPublish : LogListener
{
public:
	LogPublish(std::string service_name, std::string host);

    void AddLogEntry(const LogEntry &entry);

private:
	zmq::socket_t &GetSocket();

	zmq::context_t m_Context;
	std::string m_ServiceName;
	std::string m_Host;
};

#endif // LOGPUBLISH_H
