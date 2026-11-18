#ifndef LOGFORWARDER_H
#define LOGFORWARDER_H

#include <string>
#include <memory>
#include <cstdint>

#include "Log.h"

class MessageBroker;

class LogForwarder : LogListener
{
public:
	LogForwarder();
	~LogForwarder();

	void Connect(std::string service_id, std::shared_ptr<MessageBroker> broker);

    void AddLogEntry(const LogEntry &entry);

private:
	std::string m_ServiceId;
	std::shared_ptr<MessageBroker> m_Broker;
};

#endif // LOGFORWARDER_H
