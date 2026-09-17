#include "LogForwarder.h"

#include <nlohmann/json.hpp>
#include <iostream>

#include "LocalMessageBroker.h"

using json = nlohmann::json;

LogForwarder::LogForwarder()
	: m_Broker(nullptr)
{
}

LogForwarder::~LogForwarder()
{
}

void LogForwarder::Connect(std::string service_id, std::shared_ptr<MessageBroker> broker)
{
	m_ServiceId = service_id;
	m_Broker = broker;
}

void LogForwarder::AddLogEntry(const LogEntry &entry)
{
	if (!m_Broker)
	{
		// Broker not connected yet, skip logging
		return;
	}

	json message = {
		{"timestamp", entry.timestamp},
		{"time", entry.time},
		{"severity", ConvertSeverityToString(entry.severity)},
		{"message", entry.message},
		{"source", {
			{"service_id", m_ServiceId},
			{"file", entry.filename},
			{"line", entry.line},
			{"function", entry.function}
		}}
	};

	std::string json_message = message.dump();
	std::string topic = "logs";

	// Publish directly to MessageBroker
	m_Broker->PublishData(topic, json_message.data(), json_message.size());
}
