#ifndef SERVER_H
#define SERVER_H

#include <string>
#include <atomic>
#include <functional>
#include <map>

class Server
{
public:
	Server(int port);
	virtual ~Server();

	typedef std::function<std::string(const std::string&)> RequestHandler;

	void RegisterRequestHandler(std::string type, RequestHandler func);

	void RunServer(void (*error_check)()=nullptr);
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

#endif // SERVER_H
