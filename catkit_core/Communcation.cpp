#include "Communication.h"

Client::Client(std::string host, int port)
    : m_Host(host), m_Port(port)
{
}

zmq::socket_t Client::GetSocket()
{
	static zmq::context_t context;
	thread_local static zmq::socket_t socket(context, ZMQ_REQ);
	thread_local static bool connected(false);

	if (!connected)
	{
		socket.set(zmq::sockopt::rcvtimeo, 20);
		socket.set(zmq::sockopt::linger, 0);
		socket.set(zmq::sockopt::req_relaxed, 1);
		socket.set(zmq::sockopt::req_correlate, 1);

		socket.connect("tcp://"s + m_Host + ":" + to_string(m_Port));

		connected = true;
	}

	return socket;
}
