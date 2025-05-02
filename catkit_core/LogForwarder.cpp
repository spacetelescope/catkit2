#include "LogForwarder.h"

#include "Networking.h"

#include <zmq.h>
#include <nlohmann/json.hpp>
#include <iostream>
#include <string>
#include <thread>

using json = nlohmann::json;

LogForwarder::LogForwarder()
	: m_ShutDown(false)
{
}

LogForwarder::~LogForwarder()
{
	ShutDown();

	if (m_MessageLoopThread.joinable())
		m_MessageLoopThread.join();
}

void LogForwarder::Connect(std::string service_id, std::string host)
{
	m_ServiceId = service_id;
	m_Host = host;

	m_MessageLoopThread = std::thread(&LogForwarder::MessageLoop, this);
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
	context_t *context = (context_t *) zmq_ctx_new();
	socket_t *socket = (socket_t *) zmq_socket(context, ZMQ_PUSH);

	int linger = 0;
	int sndtimeo = 10;
	zmq_setsockopt(socket, ZMQ_LINGER, &linger, sizeof(linger));
	zmq_setsockopt(socket, ZMQ_SNDTIMEO, &sndtimeo, sizeof(sndtimeo));

	zmq_connect(socket, m_Host.c_str());

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
		while (!m_ShutDown)
		{
			if (zmq_send(socket, log_message.c_str(), log_message.size(), 0) < 0)
			{
				if (zmq_errno() == EAGAIN)
					continue;

				LOG_ERROR(std::string("Error sending message to log forwarder: ") + zmq_strerror(zmq_errno()));
				break;
			}
		}
	}

	zmq_close(socket);
	zmq_ctx_destroy(context);
}

void LogForwarder::ShutDown()
{
	m_ShutDown = true;
	m_ConditionVariable.notify_all();
}
