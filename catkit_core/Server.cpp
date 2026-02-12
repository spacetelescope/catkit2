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

#define DEBUG_PRINT(msg) std::cerr << "[DEBUG] " << __func__ << ":" << __LINE__ << " - " << msg << std::endl
#define ERROR_PRINT(msg) std::cerr << "[ERROR] " << __func__ << ":" << __LINE__ << " - " << msg << std::endl

Server::Server(int port, int num_workers)
	: m_Port(port), m_NumWorkers(num_workers), m_IsRunning(false), m_ShouldShutDown(false)
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

    // Initialize ZMQ context and socket
    m_Context = std::make_unique<zmq::context_t>();
    m_Socket = std::make_unique<zmq::socket_t>(*m_Context, ZMQ_ROUTER);
    m_Socket->bind("tcp://*:"s + std::to_string(m_Port));
    m_Socket->set(zmq::sockopt::rcvtimeo, 20);
    m_Socket->set(zmq::sockopt::linger, 0);

    LOG_INFO("Starting server on port "s + to_string(m_Port) + " with " + to_string(m_NumWorkers) + " worker(s).");

    // Start receive thread
    m_ReceiveThread = thread(&Server::ReceiveLoop, this);

    // Start worker threads
    m_WorkerThreads.reserve(m_NumWorkers);
    for (int i = 0; i < m_NumWorkers; i++) {
        m_WorkerThreads.emplace_back(&Server::WorkerLoop, this, i);
    }
}

void Server::Stop()
{
	m_ShouldShutDown = true;

    // Wake up all waiting workers
    {
        std::lock_guard<std::mutex> lock(m_QueueMutex);
        m_QueueCV.notify_all();
    }

    // Join receive thread
    if (m_ReceiveThread.joinable())
		m_ReceiveThread.join();

    // Join all worker threads
    for (auto& worker : m_WorkerThreads) {
        if (worker.joinable())
            worker.join();
    }

    // Clean up ZMQ
    if (m_Socket) {
        m_Socket->close();
        m_Socket.reset();
    }
    if (m_Context) {
        m_Context.reset();
    }

	CleanupRequestHandlers();

    m_IsRunning = false;
    LOG_INFO("Server has shut down.");
}

void Server::CleanupRequestHandlers()
{
	m_RequestHandlers.clear();
}

void Server::ReceiveLoop()
{
    LOG_DEBUG("Receive loop started.");

    while (!m_ShouldShutDown)
    {
        zmq::multipart_t request_msg;
        auto res = zmq::recv_multipart(*m_Socket, std::back_inserter(request_msg));

        if (!res.has_value())
        {
            // Server has received no message (timeout).
            continue;
        }

        if (request_msg.size() != 5)
        {
            LOG_ERROR("The server has received a message with "s + std::to_string(request_msg.size()) + " frames instead of five. Ignoring.");
            continue;
        }

        PendingRequest req;
        req.client_identity = request_msg.popstr();
        req.request_id = request_msg.popstr();
        std::string empty = request_msg.popstr();  // Empty delimiter frame
        req.request_type = request_msg.popstr();
        req.request_data = request_msg.popstr();

        DEBUG_PRINT("received: type=" << req.request_type << " client=" << req.client_identity);
        LOG_DEBUG("Request received: "s + req.request_type + " from " + req.client_identity);

        // Enqueue for workers
        {
            std::lock_guard<std::mutex> lock(m_QueueMutex);
            m_RequestQueue.push(std::move(req));
        }
        m_QueueCV.notify_one();
    }

    LOG_DEBUG("Receive loop ended.");
}

void Server::WorkerLoop(int worker_id)
{
    LOG_DEBUG("Worker "s + to_string(worker_id) + " started.");

    while (!m_ShouldShutDown)
    {
        PendingRequest req;

        // Dequeue (blocking with timeout to check shutdown periodically)
        {
            std::unique_lock<std::mutex> lock(m_QueueMutex);
            bool has_request = m_QueueCV.wait_for(lock, std::chrono::milliseconds(100), [this] {
                return !m_RequestQueue.empty() || m_ShouldShutDown.load();
            });

            if (!has_request || m_ShouldShutDown)
                continue;

            req = std::move(m_RequestQueue.front());
            m_RequestQueue.pop();
            DEBUG_PRINT("Worker " << worker_id << " dequeued request: type=" << req.request_type);
        }

        // Process request (this can take a long time, but doesn't block other workers)
        string reply_data;
        string reply_type = "OK";

        auto handler = m_RequestHandlers.find(req.request_type);

        if (handler == m_RequestHandlers.end())
        {
            LOG_ERROR("An unknown request type was received: "s + req.request_type + ".");
            reply_type = "ERROR";
            reply_data = "Unknown request type";
        }
        else
        {
            DEBUG_PRINT("Worker " << worker_id << " calling handler for: " << req.request_type);
            try
            {
                // Move request_data to handler to avoid copy (handler takes const& but we don't need it after)
                reply_data = handler->second(std::move(req.request_data));
                DEBUG_PRINT("Worker " << worker_id << " handler completed for: " << req.request_type);
            }
            catch (std::exception &e)
            {
                ERROR_PRINT("Worker " << worker_id << " exception in handler: " << e.what());
                LOG_ERROR("Encountered error during handling of request: "s + e.what());
                reply_type = "ERROR";
                reply_data = e.what();
            }
        }

        // Send reply (move reply_data since we don't need it after)
        SendResponse(req.client_identity, req.request_id, reply_type, std::move(reply_data));

        LOG_DEBUG("Worker "s + to_string(worker_id) + " sent reply: " + reply_type);
    }

    LOG_DEBUG("Worker "s + to_string(worker_id) + " ended.");
}

void Server::SendResponse(const std::string& client_identity, const std::string& request_id,
                          const std::string& reply_type, std::string reply_data)
{
    multipart_t msg;

    msg.addstr(client_identity);
    msg.addstr(request_id);
    msg.addstr("");
    msg.addstr(reply_type);
    msg.addstr(std::move(reply_data));  // Move into ZMQ message

    // ZMQ sockets are not thread-safe - must protect with mutex
    std::lock_guard<std::mutex> lock(m_SocketMutex);
    msg.send(*m_Socket);
}

bool Server::IsRunning() const
{
	return m_IsRunning;
}

int Server::GetPort() const
{
	return m_Port;
}

int Server::GetNumWorkers() const
{
    return m_NumWorkers;
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
