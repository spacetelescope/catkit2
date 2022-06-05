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

	std::string GetHost();
	int GetPort();

protected:
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

class Server
{
public:
	Server(int port);

	typedef std::function<std::string(const std::string&)> RequestHandler;

	void RegisterRequestHandler(std::string type, RequestHandler func);

	void RunServer();
	void ShutDown();

	bool ShouldShutDown();
	bool IsRunning();

	int GetPort();

	void Sleep(double sleep_time_in_ms, void (*error_check)()=nullptr);

protected:
	int m_Port;

private:
	std::map<std::string, RequestHandler> m_RequestHandlers;

	std::atomic_bool m_IsRunning;
	std::atomic_bool m_ShouldShutDown;
};

template<typename ProtoRequest>
std::string Serialize(const ProtoRequest &request);

#include "Communication.inl"

#endif // COMMUNICATION_H
