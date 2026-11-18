#include "Tracing.h"

#include "Timing.h"
#include "Util.h"
#include "Log.h"
#include "tracing.pb.h"
#include "MessageBroker.h"

using namespace std;

TracingProxy tracing_proxy;

TracingProxy::TracingProxy()
	: m_IsConnected(false)
{
}

TracingProxy::~TracingProxy()
{
	Disconnect();
}

void TracingProxy::Connect(string process_name, std::shared_ptr<MessageBroker> broker)
{
	// Disconnect if we are already running.
	if (IsConnected())
	{
		Disconnect();
	}

	SetProcessName(process_name);

	m_Broker = broker;
	m_ShutDown = false;

	m_MessageLoopThread = std::thread(&TracingProxy::MessageLoop, this);
	m_IsConnected = true;
}

void TracingProxy::Disconnect()
{
	m_ShutDown = true;
	m_ConditionVariable.notify_all();

	// Wait for the thread to exit.
	if (m_MessageLoopThread.joinable())
		m_MessageLoopThread.join();

	m_IsConnected = false;
	m_Broker.reset();
}

bool TracingProxy::IsConnected()
{
	return m_IsConnected;
}

void TracingProxy::TraceInterval(string name, string category, uint64_t timestamp, uint64_t duration)
{
	TraceEventInterval event;

	event.name = name;
	event.category = category;
	event.process_id = GetProcessId();
	event.process_name = m_ProcessName;
	event.thread_id = GetThreadId();
	event.thread_name = m_ThreadName;
	event.timestamp = timestamp;
	event.duration = duration;

	AddTraceEvent(event);
}

void TracingProxy::TraceInstant(string name, uint64_t timestamp)
{
	TraceEventInstant event;

	event.name = name;
	event.process_id = GetProcessId();
	event.process_name = m_ProcessName;
	event.thread_id = GetThreadId();
	event.thread_name = m_ThreadName;
	event.timestamp = timestamp;

	AddTraceEvent(event);
}

void TracingProxy::TraceCounter(string name, string series, uint64_t timestamp, double counter)
{
	TraceEventCounter event;

	event.name = name;
	event.series = series;
	event.process_id = GetProcessId();
	event.process_name = m_ProcessName;
	event.timestamp = timestamp;
	event.counter = counter;

	AddTraceEvent(event);
}

struct BuildProtoEvent
{
	string operator()(TraceEventInterval &event)
	{
		auto *interval = new catkit_proto::tracing::TraceEventInterval();

		interval->set_name(event.name);
		interval->set_category(event.category);
		interval->set_process_id(event.process_id);
		interval->set_process_name(event.process_name);
		interval->set_thread_id(event.thread_id);
		interval->set_thread_name(event.thread_name);
		interval->set_timestamp(event.timestamp);
		interval->set_duration(event.duration);

		catkit_proto::tracing::TraceEvent proto;
		proto.set_allocated_interval(interval);

		return proto.SerializeAsString();
	}

	string operator()(TraceEventInstant &event)
	{
		auto *instant = new catkit_proto::tracing::TraceEventInstant();

		instant->set_name(event.name);
		instant->set_process_id(event.process_id);
		instant->set_process_name(event.process_name);
		instant->set_thread_id(event.thread_id);
		instant->set_thread_name(event.thread_name);
		instant->set_timestamp(event.timestamp);

		catkit_proto::tracing::TraceEvent proto;
		proto.set_allocated_instant(instant);

		return proto.SerializeAsString();
	}

	string operator()(TraceEventCounter &event)
	{
		auto *counter = new catkit_proto::tracing::TraceEventCounter();

		counter->set_name(event.name);
		counter->set_series(event.series);
		counter->set_process_id(event.process_id);
		counter->set_process_name(event.process_name);
		counter->set_timestamp(event.timestamp);
		counter->set_counter(event.counter);

		catkit_proto::tracing::TraceEvent proto;
		proto.set_allocated_counter(counter);

		return proto.SerializeAsString();
	}
};

void TracingProxy::MessageLoop()
{
	TraceEvent event;

	while (!m_ShutDown)
	{
		// Get next message from the queue.
		{
			std::unique_lock<std::mutex> lock(m_Mutex);

			while (m_TraceMessages.empty() && !m_ShutDown)
			{
				m_ConditionVariable.wait(lock);
			}

			if (m_ShutDown)
				break;

			event = m_TraceMessages.front();
			m_TraceMessages.pop();
		}

		// Convert the TraceEvent to a ProtoBuf serialized string.
		string message = std::visit(BuildProtoEvent{}, event);

		// Publish to MessageBroker
		if (m_Broker)
		{
			std::string topic = "traces";
			m_Broker->PublishData(topic, message.data(), message.size());
		}
	}
}

void TracingProxy::SetProcessName(string process_name)
{
	m_ProcessName = process_name;
}

void TracingProxy::SetThreadName(string thread_name)
{
	m_ThreadName = thread_name;
}
