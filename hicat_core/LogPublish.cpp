#include "LogPublish.h"

#include <nlohmann/json.hpp>

using namespace zmq;
using json = nlohmann::json;

LogPublish::LogPublish(std::string service_name, std::string host)
	: m_ServiceName(service_name), m_Host(host), m_Context(1)
{

}

void LogPublish::AddLogEntry(const LogEntry &entry)
{
	auto &socket = GetSocket();

	json message = {
		{"service_name", m_ServiceName},
		{"filename", entry.filename},
		{"line", entry.line},
		{"function", entry.function},
		{"severity", ConvertSeverityToString(entry.severity)},
		{"message", entry.message},
		{"timestamp", entry.timestamp},
		{"time", entry.time}
	};

	std::string json_message = message.dump();

	// Construct and send message
	message_t message_zmq(json_message.size());
	memcpy(message_zmq.data(), json_message.c_str(), json_message.size());

	socket.send(message_zmq, zmq::send_flags::none);
}

zmq::socket_t &LogPublish::GetSocket()
{
	thread_local static socket_t socket(m_Context, ZMQ_PUB);
	thread_local static bool connected = false;

	if (!connected)
	{
		socket.connect(m_Host);
		connected = true;
	}

	return socket;
}
