#include "Server.h"

#include "Log.h"
#include "Timing.h"
#include "Finally.h"
#include "Util.h"
#include "Networking.h"

#include <zmq.h>
#include <algorithm>
#include <chrono>
#include <thread>
#include <iostream>
#include <string>
#include <vector>

using namespace std;

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

	context_t *context = (context_t *) zmq_ctx_new();

	socket_t *socket = (socket_t *) zmq_socket(context, ZMQ_ROUTER);

	if (zmq_bind(socket, ("tcp://*:"s + to_string(m_Port)).c_str()) == -1)
		throw runtime_error("Failed to bind socket. Error: "s + zmq_strerror(zmq_errno()));

	int recv_timeout = 20;
	int linger = 0;

	zmq_setsockopt(socket, ZMQ_RCVTIMEO, &recv_timeout, sizeof(int));
	zmq_setsockopt(socket, ZMQ_LINGER, &linger, sizeof(int));

	Finally finally([this, &socket, &context]()
	{
		zmq_close(socket);
		zmq_ctx_destroy(context);

		this->m_ShouldShutDown = true;
		this->m_IsRunning = false;

		LOG_INFO("Server has shut down.");
	});

	while (!m_ShouldShutDown)
	{
		std::vector<std::string> request_msg;

		if (zmq_recv_multipart(socket, std::back_inserter(request_msg)) < 0)
		{
			if (zmq_errno() != EAGAIN)
				LOG_ERROR("The server has received an error while receiving a message: "s + zmq_strerror(zmq_errno()));

			continue;
		}

		if (request_msg.size() != 5)
		{
			// Each message should have five frames: request_id, identity, empty, type and data.
			LOG_ERROR("The server has received a message with "s + std::to_string(request_msg.size()) + " frames instead of five. Ignoring.");
			continue;
		}

		std::string &client_identity = request_msg[0];
		std::string &request_id = request_msg[1];
		std::string &empty = request_msg[2];
		std::string &request_type = request_msg[3];
		std::string &request_data = request_msg[4];

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
		zmq_send(socket, client_identity.c_str(), client_identity.size(), ZMQ_SNDMORE);
		zmq_send(socket, request_id.c_str(), request_id.size(), ZMQ_SNDMORE);
		zmq_send(socket, "", 0, ZMQ_SNDMORE);
		zmq_send(socket, reply_type.c_str(), reply_type.size(), ZMQ_SNDMORE);
		zmq_send(socket, reply_data.c_str(), reply_data.size(), 0);

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
	::Sleep(sleep_time_in_sec, [this, error_check]() -> bool
	{
		if (error_check)
			error_check();

		return this->m_ShouldShutDown;
	});
}
