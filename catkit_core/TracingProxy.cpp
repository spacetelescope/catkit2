#include "TracingProxy.h"

#include "Timing.h"
#include "Util.h"
#include "Log.h"
#include "proto/tracing.pb.h"

#include <zmq.hpp>

using namespace std;

TracingProxy tracing_proxy;

TracingProxy::TracingProxy()
{
}

TracingProxy::~TracingProxy()
{
	Disconnect();
}

void TracingProxy::Connect(string host, int port)
{
	// Disconnect if we are already running.
	if (IsConnected())
	{
		if (m_Host == host && m_Port == port)
			return;

		Disconnect();
	}

	m_Host = host;
	m_Port = port;
	m_ShutDown = false;

	m_MessageLoopThread = std::thread(&TracingProxy::MessageLoop, this);
}

void TracingProxy::Disconnect()
{
	m_ShutDown = true;
	m_ConditionVariable.notify_all();

	// Wait for the thread to exit.
	if (m_MessageLoopThread.joinable())
		m_MessageLoopThread.join();
}

bool TracingProxy::IsConnected()
{
	return m_MessageLoopThread.joinable();
}

void TracingProxy::TraceInterval(string name, string category, uint64_t timestamp, uint64_t duration)
{
	TraceEventInterval event;

	event.name = name;
	event.category = category;
	event.process_id = GetProcessId();
	event.thread_id = GetThreadId();
	event.timestamp = timestamp;
	event.duration = duration;

	AddTraceEvent(event);
}

void TracingProxy::TraceInstant(string name, uint64_t timestamp)
{
	TraceEventInstant event;

	event.name = name;
	event.process_id = GetProcessId();
	event.thread_id = GetThreadId();
	event.timestamp = timestamp;

	AddTraceEvent(event);
}

void TracingProxy::TraceCounter(string name, string series, uint64_t timestamp, double counter)
{
	TraceEventCounter event;

	event.name = name;
	event.series = series;
	event.process_id = GetProcessId();
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
		interval->set_thread_id(event.thread_id);
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
		instant->set_thread_id(event.thread_id);
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
		counter->set_timestamp(event.timestamp);
		counter->set_counter(event.counter);

		catkit_proto::tracing::TraceEvent proto;
		proto.set_allocated_counter(counter);

		return proto.SerializeAsString();
	}
};

void TracingProxy::MessageLoop()
{
	zmq::context_t context;
	zmq::socket_t socket(context, ZMQ_PUSH);

	socket.set(zmq::sockopt::linger, 0);
	socket.set(zmq::sockopt::sndtimeo, 10);

	socket.connect("tcp://"s + m_Host + ":" + to_string(m_Port));

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

		// Construct message.
		zmq::message_t message_zmq(message.size());
		memcpy(message_zmq.data(), message.c_str(), message.size());

		// Send message to socket.
		zmq::send_result_t res;
		do
		{
			res = socket.send(message_zmq, zmq::send_flags::none);
		}
		while (!res.has_value() && m_ShutDown);
	}

	socket.close();
}
