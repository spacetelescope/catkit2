#include "Server.h"

#include "Log.h"
#include "Timing.h"
#include "Finally.h"
#include "Util.h"

#include <zmq_addon.hpp>

#include <algorithm>
#include <chrono>
#include <thread>
#include <iostream>
#include <string>

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

	if (m_ShouldShutDown)
		throw runtime_error("This server can only run once.");

	m_IsRunning = true;

    m_RunThread = thread(&Server::RunInternal, this);
}

void Server::Stop()
{
	m_ShouldShutDown = true;

	if (m_RunThread.joinable())
		m_RunThread.join();

	CleanupRequestHandlers();
}

void Server::CleanupRequestHandlers()
{
	m_RequestHandlers.clear();
}

void Server::RunInternal()
{
	LOG_INFO("Starting server on port "s + to_string(m_Port) + ".");

	zmq::context_t context;

	zmq::socket_t socket(context, ZMQ_ROUTER);
	// Bind and configure socket inside a try/catch so ZMQ errors are handled
	try
	{
		socket.bind("tcp://*:"s + std::to_string(m_Port));
		socket.set(zmq::sockopt::rcvtimeo, 20);
		socket.set(zmq::sockopt::linger, 0);
	}
	catch (const zmq::error_t &e)
	{
		LOG_ERROR("Failed to bind server socket on port "s + std::to_string(m_Port) + ": "s + e.what());
		// Ensure we mark server as not running and request shutdown
		this->m_ShouldShutDown = true;
		this->m_IsRunning = false;
		try {
			socket.close();
		} catch (...) {}
		return;
	}

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
			// Copy frames to strings for easier inspection.
			std::vector<std::string> parts;
			parts.reserve(request_msg.size());
			for (size_t i = 0; i < request_msg.size(); ++i)
			{
				auto &frame = request_msg.at(i);
				size_t sz = frame.size();
				parts.emplace_back(reinterpret_cast<const char*>(frame.data()), sz);
			}

			// Try to salvage: look for a subsequence matching [request_id, "", request_type, data]
			// where request_type is a registered handler.
			int salvage_index = -1;
			for (size_t p = 0; p + 3 < parts.size(); ++p)
			{
				// parts[p] = request_id, parts[p+1] = empty, parts[p+2] = type
				if (!parts[p+1].empty())
					continue;

				std::string candidate_type = parts[p+2];
				if (m_RequestHandlers.find(candidate_type) != m_RequestHandlers.end())
				{
					salvage_index = static_cast<int>(p);
					break;
				}
			}

		if (salvage_index >= 0)
		{
			// Use the first frame as client identity (best-effort) and extract
			// the request fields from salvage_index..salvage_index+3.
			std::string client_identity = parts.front();
			std::string request_id = parts[salvage_index];
			std::string empty = parts[salvage_index + 1];
			std::string request_type = parts[salvage_index + 2];
			std::string request_data = parts[salvage_index + 3];				// Call handler directly.
			string reply_data;
			string reply_type = "OK";

			auto handler = m_RequestHandlers.find(request_type);
			if (handler == m_RequestHandlers.end())
			{
				LOG_ERROR("Unknown request type in salvaged message: "s + request_type + ".");
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
					LOG_ERROR("Encountered error during handling of salvaged request: "s + e.what());
					reply_type = "ERROR";
					reply_data = e.what();
				}
			}

			// Send reply to the client using the full identity envelope (all frames
			// before the salvaged request). This preserves routing through
			// intermediaries which may have added multiple identity frames.
			multipart_t msg;
			for (int idf = 0; idf < salvage_index; ++idf)
			{
				msg.addstr(parts[idf]);
			}
			msg.addstr(request_id);
			msg.addstr("");
			msg.addstr(reply_type);
			msg.addstr(reply_data);

			msg.send(socket);

			// Move to next loop iteration.
			continue;
			}

			// If salvage failed, log error and ignore.
			LOG_ERROR("The server received a malformed message with "s + to_string(request_msg.size()) + " frames instead of 5.");
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
	::Sleep(sleep_time_in_sec, [this, error_check]() -> bool
	{
		if (error_check)
			error_check();

		return this->m_ShouldShutDown;
	});
}
