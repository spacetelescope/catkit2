#ifndef CLIENT_H
#define CLIENT_H

#include "Networking.h"

#include <string>
#include <mutex>
#include <functional>
#include <memory>
#include <stack>

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

	void *m_Context;

	typedef std::unique_ptr<socket_t, std::function<void(socket_t *)>> socket_ptr;
	socket_ptr GetSocket();

	std::mutex m_Mutex;
	std::stack<socket_t *> m_Sockets;
};

template<typename ProtoRequest>
std::string Serialize(const ProtoRequest &request);

#endif // CLIENT_H
