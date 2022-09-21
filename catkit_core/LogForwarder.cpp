#include "LogForwarder.h"

#include <nlohmann/json.hpp>
#include <iostream>

using namespace zmq;
using json = nlohmann::json;

LogForwarder::LogForwarder(std::string service_id, std::string host)
	: m_ServiceId(service_id), m_Host(host), m_ShutDown(false)
{
	m_MessageLoopThread = std::thread(&LogForwarder::MessageLoop, this);
}

LogForwarder::~LogForwarder()
{
	ShutDown();

	if (m_MessageLoopThread.joinable())
		m_MessageLoopThread.join();
}

void LogForwarder::AddLogEntry(const LogEntry &entry)
{
	json message = {
		{"service_id", m_ServiceId},
		{"filename", entry.filename},
		{"line", entry.line},
		{"function", entry.function},
		{"severity", ConvertSeverityToString(entry.severity)},
		{"message", entry.message},
		{"timestamp", entry.timestamp},
		{"time", entry.time}
	};

	std::string json_message = message.dump();

	std::unique_lock<std::mutex> lock(m_Mutex);
	m_LogMessages.push(json_message);

	m_ConditionVariable.notify_all();
}

void LogForwarder::MessageLoop()
{
	context_t context;
	socket_t socket(context, ZMQ_PUSH);

	socket.set(zmq::sockopt::linger, 0);
	socket.set(zmq::sockopt::sndtimeo, 10);
	socket.connect(m_Host);

	std::string log_message;

	while (!m_ShutDown)
	{
		// Get next message from the queue.
		{
			std::unique_lock<std::mutex> lock(m_Mutex);

			while (m_LogMessages.empty() && !m_ShutDown)
			{
				m_ConditionVariable.wait(lock);
			}

			if (m_ShutDown)
				break;

			log_message = m_LogMessages.front();
			m_LogMessages.pop();
		}

		// Construct and send message.
		message_t message_zmq(log_message.size());
		memcpy(message_zmq.data(), log_message.c_str(), log_message.size());

		send_result_t res;
		do
		{
			res = socket.send(message_zmq, zmq::send_flags::none);
		}
		while (!res.has_value() && !m_ShutDown);
	}

	socket.close();
}

void LogForwarder::ShutDown()
{
	m_ShutDown = true;
	m_ConditionVariable.notify_all();
}
