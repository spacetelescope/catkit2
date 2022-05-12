#include "Communication.h"

#include "Log.h"

using namespace std;
using namespace zmq;

Client::Client(std::string host, int port)
    : m_Host(host), m_Port(port)
{
}

Client::socket_ptr Client::GetSocket()
{
	static zmq::context_t context;

	std::scoped_lock<std::mutex> lock(m_Mutex);

	zmq::socket_t *socket;
	if (m_Sockets.empty())
	{
		socket = new zmq::socket_t(context, ZMQ_REQ);

		socket->set(zmq::sockopt::rcvtimeo, 20);
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

		std::string request_id = request_msg.popstr();
		std::string client_identity = request_msg.popstr();
		std::string empty = request_msg.popstr();
		std::string request_type = request_msg.popstr();
		std::string request_data = request_msg.popstr();

		LOG_DEBUG("Request received: "s + request_type);

		// Find the correct request handler.
		auto handler = m_RequestHandlers.find(request_type);

		if (handler == m_RequestHandlers.end())
		{
			LOG_ERROR("An unknown request type was received: "s + request_type + ". Ignoring message.");
			continue;
		}

		// Call the request handler and return the result if no error occurred.
		string reply_data;
		string reply_type = "OK";

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
	m_ShouldShutDown = true;
}
