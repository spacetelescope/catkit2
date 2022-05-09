#ifndef COMMUNICATION_H
#define COMMUNICATION_H

#include <string>
#include <zmq.hpp>

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
	zmq::socket_t &GetSocket();

	std::vector<zmq::socket_t> m_Sockets;
	std::vector<std::atomic_bool> m_InUse;
}

class Server
{
public:
	Server(int port);

	typedef std::function<std::string(const std::string&)> RequestHandler;

	void RegisterRequestHandler(std::string type, RequestHandler func);

	void RunServer();

protected:
	int m_Port;

private:
	std::map<std::string, RequestHandler> m_RequestHandlers;
}

#include "Communication.inl"

#endif // COMMUNICATION_H
