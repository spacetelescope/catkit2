#ifndef SERVER_H
#define SERVER_H

#include <string>
#include <atomic>
#include <functional>
#include <map>
#include <thread>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <vector>
#include <memory>

// Forward declaration for ZMQ
namespace zmq {
    class socket_t;
    class context_t;
}

struct PendingRequest {
    std::string client_identity;
    std::string request_id;
    std::string request_type;
    std::string request_data;
};

class Server
{
public:
	Server(int port, int num_workers = 1);
	virtual ~Server();

	typedef std::function<std::string(const std::string&)> RequestHandler;

	void RegisterRequestHandler(std::string type, RequestHandler func);

	void Start();
	void Stop();

	bool IsRunning();

	int GetPort();
	int GetNumWorkers() const;

	void Sleep(double sleep_time_in_sec, void (*error_check)()=nullptr);

	void CleanupRequestHandlers();

protected:
	int m_Port;
	int m_NumWorkers;

private:
    void ReceiveLoop();
    void WorkerLoop(int worker_id);
    void SendResponse(const std::string& client_identity, const std::string& request_id,
                      const std::string& reply_type, std::string reply_data);

    // Thread management
    std::thread m_ReceiveThread;
    std::vector<std::thread> m_WorkerThreads;

    // Thread pool queue
    std::queue<PendingRequest> m_RequestQueue;
    std::mutex m_QueueMutex;
    std::condition_variable m_QueueCV;

    // ZMQ context and socket (owned by Server)
    std::unique_ptr<zmq::context_t> m_Context;
    std::unique_ptr<zmq::socket_t> m_Socket;
    std::mutex m_SocketMutex;  // Protects socket operations (ZMQ sockets are not thread-safe)

	std::map<std::string, RequestHandler> m_RequestHandlers;

	std::atomic_bool m_IsRunning;
	std::atomic_bool m_ShouldShutDown;
};

#endif // SERVER_H
