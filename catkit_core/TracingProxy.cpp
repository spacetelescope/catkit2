#include "TracingProxy.h"

#include "Timing.h"
#include "Util.h"

#include "proto/tracing.pb.h"

using namespace std;

void AddProcessThreadIds(string &contents)
{
	contents += ",\"pid\":";
	contents += to_string(GetProcessId());
	contents += ",\"tid\":";
	contents += to_string(GetThreadId());
}

TracingProxy::TracingProxy(std::string host, int port)
	: m_Host(host), m_Port(port)
{
	m_MessageLoopThread = std::thread(&TracingProxy::MessageLoop, this);
}

TracingProxy::~TracingProxy()
{
	ShutDown();

	if (m_MessageLoopThread.joinable())
		m_MessageLoopThread.join();
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
		catkit_proto::tracing::TraceEventInterval proto;

		proto.set_name(event.name);
		proto.set_category(event.category);
		proto.set_process_id(event.process_id);
		proto.set_thread_id(event.thread_id);
		proto.set_timestamp(event.timestamp);
		proto.set_duration(event.duration);

		return proto.SerializeAsString();
	}

	string operator()(TraceEventInstant &event)
	{
		catkit_proto::tracing::TraceEventInstant proto;

		proto.set_name(event.name);
		proto.set_process_id(event.process_id);
		proto.set_thread_id(event.thread_id);
		proto.set_timestamp(event.timestamp);

		return proto.SerializeAsString();
	}

	string operator()(TraceEventCounter &event)
	{
		catkit_proto::tracing::TraceEventCounter proto;

		proto.set_name(event.name);
		proto.set_series(event.series);
		proto.set_process_id(event.process_id);
		proto.set_timestamp(event.timestamp);
		proto.set_counter(event.counter);

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

void TracingProxy::ShutDown()
{
	m_ShutDown = true;
	m_ConditionVariable.notify_all();
}
