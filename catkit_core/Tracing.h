#ifndef TRACING_PROXY_H
#define TRACING_PROXY_H

#include <thread>
#include <atomic>
#include <queue>
#include <condition_variable>
#include <variant>

struct TraceEventInterval
{
	std::string name;
	std::string category;
	std::uint32_t process_id;
	std::string process_name;
	std::uint32_t thread_id;
	std::string thread_name;
	std::uint64_t timestamp;
	std::uint64_t duration;
};

struct TraceEventInstant
{
	std::string name;
	std::uint32_t process_id;
	std::string process_name;
	std::uint32_t thread_id;
	std::string thread_name;
	std::uint64_t timestamp;
};

struct TraceEventCounter
{
	std::string name;
	std::string series;
	std::uint32_t process_id;
	std::string process_name;
	std::uint64_t timestamp;
	double counter;
};

typedef std::variant<TraceEventInterval, TraceEventInstant, TraceEventCounter> TraceEvent;

class TracingProxy
{
public:
	TracingProxy();
	~TracingProxy();

	void Connect(std::string process_name, std::string host, int port);
	void Disconnect();
	bool IsConnected();

	void TraceInterval(std::string name, std::string category, uint64_t timestamp_start, uint64_t duration);
	void TraceInstant(std::string name, uint64_t timestamp);
	void TraceCounter(std::string name, std::string series, uint64_t timestamp, double counter);

private:
	template<typename T>
	void AddTraceEvent(T &event)
	{
		if (IsConnected())
		{
			std::unique_lock<std::mutex> lock(m_Mutex);
			m_TraceMessages.emplace(event);

			m_ConditionVariable.notify_all();
		}
	}

	void MessageLoop();

	void SetProcessName(std::string process_name);
	void SetThreadName(std::string thread_name);

	std::thread m_MessageLoopThread;
	std::atomic_bool m_ShutDown;

	std::queue<TraceEvent> m_TraceMessages;
	std::mutex m_Mutex;
	std::condition_variable m_ConditionVariable;

	std::string m_Host;
	int m_Port;

	std::string m_ProcessName;
	std::string m_ThreadName;
};

extern TracingProxy tracing_proxy;

#endif // TRACING_PROXY_H
