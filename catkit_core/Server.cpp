#include "Server.h"

#include "Log.h"
#include "TimeStamp.h"
#include "Finally.h"
#include "Util.h"

#include <zmq_addon.hpp>

#include <algorithm>
#include <chrono>
#include <thread>
#include <iostream>

using namespace std;
using namespace zmq;

Server::Server(int port)
	: m_Port(port), m_IsRunning(false), m_ShouldShutDown(false)
{
}

Server::~Server()
{
    Stop();
}

void Server::RegisterRequestHandler(std::string type, RequestHandler func)
{
	m_RequestHandlers[type] = func;
}

void Server::Start()
{
    if (IsRunning())
        throw runtime_error("This server is already running.");

	m_ShouldShutDown = false;
	m_IsRunning = true;

    m_RunThread = thread(&Server::RunInternal, this);
}

void Server::Stop()
{
	m_ShouldShutDown = true;

	if (m_RunThread.joinable())
		m_RunThread.join();
}

void Server::RunInternal()
{
	LOG_INFO("Starting server on port "s + to_string(m_Port) + ".");

	zmq::context_t context;

	zmq::socket_t socket(context, ZMQ_ROUTER);
	socket.bind("tcp://*:"s + std::to_string(m_Port));
	socket.set(zmq::sockopt::rcvtimeo, 20);
	socket.set(zmq::sockopt::linger, 0);

	Finally finally([this, &socket]()
	{
		socket.close();

		this->m_ShouldShutDown = true;
		this->m_IsRunning = false;

		LOG_INFO("Server has shut down.");
	});

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
}

bool Server::IsRunning()
{
	return m_IsRunning;
}

int Server::GetPort()
{
	return m_Port;
}

void Server::Sleep(double sleep_time_in_sec, void (*error_check)())
{
	Sleep(sleep_time_in_sec, [this, &error_check]()
	{
		if (error_check)
			error_check();

		return this->m_ShouldShutDown;
	})
}
