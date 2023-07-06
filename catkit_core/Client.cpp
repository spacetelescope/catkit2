#include "Client.h"

#include "Log.h"
#include "Timing.h"
#include "Finally.h"

#include <zmq_addon.hpp>

#include <algorithm>
#include <chrono>
#include <thread>
#include <iostream>

using namespace std;
using namespace zmq;

const int SOCKET_TIMEOUT = 60000;  // milliseconds.

Client::Client(std::string host, int port)
    : m_Host(host), m_Port(port)
{
}

Client::~Client()
{
}

string Client::MakeRequest(const string &what, const string &request)
{
    auto socket = GetSocket();

	zmq::multipart_t request_msg;

	request_msg.addstr(what);
	request_msg.addstr(request);

	request_msg.send(*socket);

	Timer timer;

	try
	{
		zmq::multipart_t reply_msg;
		auto res = zmq::recv_multipart(*socket, std::back_inserter(reply_msg));

		if (!res.has_value())
		{
			LOG_ERROR("The server took too long to respond to our request.");
			throw std::runtime_error("The server did not respond in time. Is it running?");
		}

		if (reply_msg.size() != 2)
		{
			LOG_ERROR("The server responded with " + std::to_string(reply_msg.size()) + " parts rather than 2.");
			throw std::runtime_error("The server responded in a wrong format.");
		}

		std::string reply_type = reply_msg.popstr();
		std::string reply_data = reply_msg.popstr();

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
	}
	catch (const zmq::error_t &e)
	{
		LOG_ERROR(std::string("ZeroMQ error: ") + e.what());
		throw;
	}
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

	zmq::socket_t *socket;
	if (m_Sockets.empty())
	{
		LOG_DEBUG("Creating new socket.");

		socket = new zmq::socket_t(m_Context, ZMQ_REQ);

		socket->set(zmq::sockopt::rcvtimeo, SOCKET_TIMEOUT);
		socket->set(zmq::sockopt::linger, 0);
		socket->set(zmq::sockopt::req_relaxed, 1);
		socket->set(zmq::sockopt::req_correlate, 1);

		socket->connect("tcp://"s + m_Host + ":" + to_string(m_Port));
	}
	else
	{
		socket = m_Sockets.top().release();
		m_Sockets.pop();
	}

	return socket_ptr(socket, [this](zmq::socket_t *ptr)
		{
			this->m_Sockets.emplace(ptr);
		});
}