#include "TracingProxy.h"

#include "Time.h"
#include "Util.h"

using namespace std;

void AddProcessThreadIds(string &contents)
{
	contents += ",\"pid\":";
	contents += to_string(GetProcessId());
	contents += ",\"tid\":";
	contents += to_string(GetThreadId());
}

TracingProxy::TracingProxy(std::shared_ptr<TestbedProxy> testbed)
{
	m_Host = testbed->GetHost();
	m_Port = testbed->GetTracingIngressPort();

	m_MessageLoopThread = std::thread(&TracingProxy::MessageLoop, this);
}

TracingProxy::~TracingProxy()
{
	ShutDown();

	if (m_MessageLoopThread.joinable())
		m_MessageLoopThread.join();
}

void TracingProxy::TraceBegin(string func, string what)
{
	auto ts = GetTimeStamp();

	string contents = "{\"name\":\"";
	contents += func;
	contents += "\",\"cat\":\"\",\"ph\":\"B\",\"ts\":";
	contents += to_string(double(ts) / 1000);
	AddProcessThreadIds(contents);
	contents += ",\"args\":{\"what\":\"";
	contents += what;
	contents += "\"}}";

	SendTraceMessage(contents);
}

void TracingProxy::TraceEnd(string func)
{
	auto ts = GetTimeStamp();

	string contents = "{\"name\":\"";
	contents += func;
	contents += "\",\"cat\":\"\",\"ph\":\"E\",\"ts\":";
	contents += to_string(double(ts) / 1000);
	AddProcessThreadIds(contents);
	contents += ",}";

	SendTraceMessage(contents);
}

void TracingProxy::TraceInterval(string func, string what, uint64_t timestamp_start, uint64_t timestamp_end)
{
	string contents = "{\"name\":\"";
	contents += func;
	contents += "\",\"cat\":\"\",\"ph\":\"X\",\"ts\":";
	contents += to_string(double(timestamp_start) / 1000);
	AddProcessThreadIds(contents);
	contents += "\"dur\":";
	contents += to_string(double(timestamp_end - timestamp_start) / 1000);
	contents += ",\"args\":{\"what\":\"";
	contents += what;
	contents += "\"}}";

	SendTraceMessage(contents);
}

void TracingProxy::TraceCounter(string func, string series, double counter)
{
	auto ts = GetTimeStamp();
	string contents = "{\"name\":\"";
	contents += func;
	contents += "\",\"cat\":\"\",\"ph\":\"C\",\"ts\":";
	contents += to_string(double(ts) / 1000);
	AddProcessThreadIds(contents);
	contents += ",\"args\":{\"";
	contents += series;
	contents += "\":";
	contents += to_string(counter);
	contents += "}}";

	SendTraceMessage(contents);
}

void TracingProxy::TraceProcessName(string process_name)
{
	string contents = "{\"name\":\"process_name\",\"ph\":\"M\"";
	AddProcessThreadIds(contents);
	contents += ",\"args\":{\"name\":\"";
	contents += process_name;
	contents += "}}";

	SendTraceMessage(contents);
}

void TracingProxy::TraceThreadName(string thread_name)
{
	string contents = "{\"name\":\"thread_name\",\"ph\":\"M\"";
	AddProcessThreadIds(contents);
	contents += ",\"args\":{\"name\":\"";
	contents += thread_name;
	contents += "}}";

	SendTraceMessage(contents);
}

void TracingProxy::SendTraceMessage(string contents)
{
	std::unique_lock<std::mutex> lock(m_Mutex);
	m_TraceMessages.push(contents);

	m_ConditionVariable.notify_all();
}

void TracingProxy::MessageLoop()
{
	zmq::context_t context;
	zmq::socket_t socket(context, ZMQ_PUSH);

	socket.set(zmq::sockopt::linger, 0);
	socket.set(zmq::sockopt::sndtimeo, 10);

	socket.connect("tcp://"s + m_Host + ":" + to_string(m_Port));

	std::string message;

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

			message = m_TraceMessages.front();
			m_TraceMessages.pop();
		}

		// Construct message.
		zmq::message_t message_zmq(message.size());
		memcpy(message_zmq.data(), message.c_str(), message.size());

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
