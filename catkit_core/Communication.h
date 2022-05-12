#ifndef COMMUNICATION_H
#define COMMUNICATION_H

#include <string>
#include <zmq.hpp>
#include <atomic>
#include <mutex>
#include <stack>
#include <map>
#include <functional>

class Client
{
public:
	Client(std::string host, int port);

protected:
	std::string m_Host;
	int m_Port;

	template<typename ProtoRequest, typename ProtoReply>
	void MakeRequest(const std::string &what, const ProtoRequest &request, ProtoReply &reply);

private:
	typedef std::unique_ptr<zmq::socket_t, std::function<void(zmq::socket_t *)>> socket_ptr;
	socket_ptr GetSocket();

	std::mutex m_Mutex;
	std::stack<std::unique_ptr<zmq::socket_t>> m_Sockets;
};

class Server
{
public:
	Server(int port);

	typedef std::function<std::string(const std::string&)> RequestHandler;

	void RegisterRequestHandler(std::string type, RequestHandler func);

	void RunServer();
	void ShutDown();

protected:
	int m_Port;

	std::atomic_bool m_IsRunning;
	std::atomic_bool m_ShouldShutDown;

private:
	std::map<std::string, RequestHandler> m_RequestHandlers;
};

#include "Communication.inl"

#endif // COMMUNICATION_H
