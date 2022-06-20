#include "Communication.h"

#include "Log.h"
#include "TimeStamp.h"

#include <zmq_addon.hpp>

#include <algorithm>
#include <chrono>
#include <thread>
#include <iostream>

using namespace std;
using namespace zmq;

Client::Client(std::string host, int port)
    : m_Host(host), m_Port(port)
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

		socket->set(zmq::sockopt::rcvtimeo, 2000);
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

Server::Server(int port)
	: m_Port(port), m_IsRunning(false), m_ShouldShutDown(false)
{
}

void Server::RegisterRequestHandler(std::string type, RequestHandler func)
{
	m_RequestHandlers[type] = func;
}

void Server::RunServer()
{
	m_IsRunning = true;
	m_ShouldShutDown = false;

	LOG_INFO("Starting server on port "s + to_string(m_Port) + ".");

	zmq::context_t context;

	zmq::socket_t socket(context, ZMQ_ROUTER);
	socket.bind("tcp://*:"s + std::to_string(m_Port));
	socket.set(zmq::sockopt::rcvtimeo, 20);
	socket.set(zmq::sockopt::linger, 0);

	while (!m_ShouldShutDown)
	{
		zmq::multipart_t request_msg;
		auto res = zmq::recv_multipart(socket, std::back_inserter(request_msg));

		if (!res.has_value())
		{
			// Server has received no message.
			continue;
		}

		if (request_msg.size() != 5)
		{
			// Each message should have five frames: request_id, identity, empty, type and data.
			LOG_ERROR("The server has received a message with "s + std::to_string(request_msg.size()) + " frames instead of five. Ignoring.");
			continue;
		}

		std::string client_identity = request_msg.popstr();
		std::string request_id = request_msg.popstr();
		std::string empty = request_msg.popstr();
		std::string request_type = request_msg.popstr();
		std::string request_data = request_msg.popstr();

		LOG_DEBUG("Request received: "s + request_type);

		// Call the request handler and return the result if no error occurred.
		string reply_data;
		string reply_type = "OK";

		// Find the correct request handler.
		auto handler = m_RequestHandlers.find(request_type);

		if (handler == m_RequestHandlers.end())
		{
			LOG_ERROR("An unknown request type was received: "s + request_type + ".");
			reply_type = "ERROR";
			reply_data = "Unknown request type";
		}
		else
		{
			try
			{
				reply_data = handler->second(request_data);
			}
			catch (std::exception &e)
			{
				LOG_ERROR("Encountered error during handling of request: "s + e.what());

				reply_type = "ERROR";
				reply_data = e.what();
			}
		}

		// Send reply to the client.
		multipart_t msg;

		msg.addstr(client_identity);
		msg.addstr(request_id);
		msg.addstr("");
		msg.addstr(reply_type);
		msg.addstr(reply_data);

		msg.send(socket);

		LOG_DEBUG("Sent reply: "s + reply_type);
	}

	socket.close();

	LOG_INFO("Server has shut down.");

	m_IsRunning = false;
	m_ShouldShutDown = true;
}

void Server::ShutDown()
{
	LOG_INFO("Shut down called.");
	m_ShouldShutDown = true;
}

bool Server::ShouldShutDown()
{
	return m_ShouldShutDown;
}

bool Server::IsRunning()
{
	return m_IsRunning;
}

int Server::GetPort()
{
	return m_Port;
}

void Server::Sleep(double sleep_time_in_ms, void (*error_check)())
{
	Timer timer;

	while (true)
	{
		double sleep_remaining = sleep_time_in_ms - timer.GetTime() * 1000;

		if (sleep_remaining > 0)
			break;

		if (m_ShouldShutDown)
			break;

		if (error_check)
			error_check();

		std::this_thread::sleep_for(std::chrono::duration<double, std::milli>(std::min(double(1.0), sleep_remaining)));
	}
}
