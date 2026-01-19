#ifndef CLIENT_H
#define CLIENT_H

#include <string>
#include <mutex>
#include <functional>
#include <memory>
#include <stack>

#include <zmq.hpp>

class Client
{
public:
	Client(std::string host, int port);
	virtual ~Client();

	std::string GetHost();
	int GetPort();

	std::string MakeRequest(const std::string &what, const std::string &request);

private:
	std::string m_Host;
	int m_Port;

	zmq::context_t m_Context;

	typedef std::unique_ptr<zmq::socket_t, std::function<void(zmq::socket_t *)>> socket_ptr;
	socket_ptr GetSocket();

	std::mutex m_Mutex;
	std::stack<std::unique_ptr<zmq::socket_t>> m_Sockets;
};

template<typename ProtoRequest>
std::string Serialize(const ProtoRequest &request);

#endif // CLIENT_H
