#include "TracingProxy.h"

#include "TimeStamp.h"
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
	contents += process_name;
	contents += "}}";

	SendTraceMessage(contents);
}

void TracingProxy::SendTraceMessage(string contents)
{
	thread_local static zmq::socket_t socket(m_Context, ZMQ_PUSH);
	thread_local static bool connected(false);

	if (!connected)
	{
		socket.connect("tcp://"s + m_Host + ":" + to_string(m_Port));
		connected = true;
	}

	socket.send_string(contents);
}
