#include "Client.h"

#include "Log.h"
#include "Timing.h"
#include "Finally.h"

#include <algorithm>
#include <chrono>
#include <thread>
#include <iostream>
#include <string>
#include <mutex>
#include <zmq.h>

using namespace std;

const int SOCKET_TIMEOUT = 60000;  // milliseconds.

Client::Client(std::string host, int port)
    : m_Host(host), m_Port(port)
{
	m_Context = zmq_ctx_new();
}

Client::~Client()
{
	while (!m_Sockets.empty())
	{
		zmq_close(m_Sockets.top());
		m_Sockets.pop();
	}

	zmq_ctx_term(m_Context);
}

string Client::MakeRequest(const string &what, const string &request)
{
    auto socket = GetSocket();

	// Send the request.
	zmq_send(socket.get(), what.c_str(), what.size(), ZMQ_SNDMORE);
	zmq_send(socket.get(), request.c_str(), request.size(), 0);

	Timer timer;
	int more = 1;
	std::vector<std::string> response;

	if (zmq_recv_multipart(socket.get(), std::back_inserter(response)) < 0)
	{
		if (zmq_errno() == EAGAIN)
		{
			LOG_ERROR("The server took too long to respond to our request.");
			throw std::runtime_error("The server did not respond in time. Is it running?");
		}
		else
		{
			LOG_ERROR("An error occurred while sending the request to the server: "s + zmq_strerror(zmq_errno()));
			throw std::runtime_error("An error occurred while sending the request to the server.");
		}
	}

	if (response.size() != 2)
	{
		LOG_ERROR("The server did not respond with the expected number of parts.");
		throw std::runtime_error("The server responded in a wrong format.");
	}

	const std::string &reply_type(response[0]);
	const std::string &reply_data(response[1]);

	if (reply_type == "OK")
	{
		return reply_data;
	}
	else if (reply_type == "ERROR")
	{
		throw std::runtime_error(reply_data);
	}
	else
	{
		LOG_ERROR("The server responded with \"" + reply_type + "\" rather than OK or ERROR.");
		throw std::runtime_error("The server responded in a wrong format.");
	}

	return reply_data;
}

std::string Client::GetHost()
{
	return m_Host;
}

int Client::GetPort()
{
	return m_Port;
}

Client::socket_ptr Client::GetSocket()
{
	std::scoped_lock<std::mutex> lock(m_Mutex);

	socket_t *socket;
	if (m_Sockets.empty())
	{
		LOG_DEBUG("Creating new socket.");

		socket = (socket_t *) zmq_socket(m_Context, ZMQ_REQ);

		int timeout = SOCKET_TIMEOUT;
		int linger = 0;
		int req_relaxed = 1;
		int req_correlate = 1;

		zmq_setsockopt(socket, ZMQ_RCVTIMEO, &timeout, sizeof(int));
		zmq_setsockopt(socket, ZMQ_LINGER, &linger, sizeof(int));
		zmq_setsockopt(socket, ZMQ_REQ_RELAXED, &req_relaxed, sizeof(int));
		zmq_setsockopt(socket, ZMQ_REQ_CORRELATE, &req_correlate, sizeof(int));

		std::string endpoint = "tcp://"s + m_Host + ":" + to_string(m_Port);
		if (zmq_connect(socket, endpoint.c_str()) == -1)
		{
			LOG_ERROR("Failed to connect to " + endpoint);
			throw std::runtime_error("Failed to connect to " + endpoint);
		}
	}
	else
	{
		socket = m_Sockets.top();
		m_Sockets.pop();
	}

	return socket_ptr(socket, [this](socket_t *ptr)
		{
			this->m_Sockets.emplace(ptr);
		});
}
