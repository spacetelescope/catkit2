#include "TestbedProxy.h"

#include "Timing.h"
#include "proto/testbed.pb.h"

#include <memory>

using namespace std;
using namespace zmq;
using json = nlohmann::json;
using namespace std::string_literals;

const double HEARTBEAT_LIVENESS = 30;

TestbedProxy::TestbedProxy(std::string host, int port)
	: Client(host, port), m_Host(host), m_Port(port), m_HasGottenInfo(false)
{
	// TODO: Maybe to a check early on to see if something is listening on this port.
}

TestbedProxy::~TestbedProxy()
{
}

std::shared_ptr<ServiceProxy> TestbedProxy::GetService(const std::string &service_id)
{
	auto service_iterator = m_Services.find(service_id);

	if (service_iterator == m_Services.end())
	{
		m_Services[service_id] = std::make_shared<ServiceProxy>(shared_from_this(), service_id);

		service_iterator = m_Services.find(service_id);
	}

	return service_iterator->second;
}

void TestbedProxy::StartService(const std::string &service_id)
{
	catkit_proto::testbed::StartServiceRequest request;
	request.set_service_id(service_id);

	catkit_proto::testbed::StartServiceReply reply;

	try
	{
		reply.ParseFromString(MakeRequest("start_service", Serialize(request)));
	}
	catch (...)
	{
		throw std::runtime_error("Unable to start service.");
	}
}

void TestbedProxy::StartServices(std::vector<std::string> service_ids)
{
	for (const std::string &service_id : service_ids)
		StartService(service_id);
}

void TestbedProxy::StopService(const std::string &service_id)
{
	catkit_proto::testbed::StopServiceRequest request;
	request.set_service_id(service_id);

	catkit_proto::testbed::StopServiceReply reply;

	try
	{
		reply.ParseFromString(MakeRequest("stop_service", Serialize(request)));
	}
	catch (...)
	{
		throw std::runtime_error("Unable to stop service.");
	}
}

void TestbedProxy::InterruptService(const std::string &service_id)
{
	catkit_proto::testbed::InterruptServiceRequest request;
	request.set_service_id(service_id);

	catkit_proto::testbed::InterruptServiceReply reply;

	try
	{
		reply.ParseFromString(MakeRequest("interrupt_service", Serialize(request)));
	}
	catch (...)
	{
		throw std::runtime_error("Unable to interrupt service.");
	}
}

void TestbedProxy::TerminateService(const std::string &service_id)
{
	catkit_proto::testbed::TerminateServiceRequest request;
	request.set_service_id(service_id);

	catkit_proto::testbed::TerminateServiceReply reply;

	try
	{
		reply.ParseFromString(MakeRequest("terminate_service", Serialize(request)));
	}
	catch (...)
	{
		throw std::runtime_error("Unable to terminate service.");
	}
}

ServiceReference TestbedProxy::GetServiceInfo(const std::string &service_id)
{
	catkit_proto::testbed::GetServiceInfoRequest request;
	request.set_service_id(service_id);

	catkit_proto::testbed::GetServiceInfoReply reply;

	try
	{
		reply.ParseFromString(MakeRequest("get_service_info", Serialize(request)));
	}
	catch (...)
	{
		throw std::runtime_error("Unable to get service info.");
	}

	ServiceReference res;

	res.id = reply.service().id();
	res.type = reply.service().type();
	res.state_stream_id = reply.service().state_stream_id();
	res.host = reply.service().host();
	res.port = reply.service().port();

	return res;
}

std::string TestbedProxy::RegisterService(std::string service_id, std::string service_type, std::string host, int port, int process_id, std::string heartbeat_stream_id)
{
	catkit_proto::testbed::RegisterServiceRequest request;

	request.set_service_id(service_id);
	request.set_service_type(service_type);
	request.set_host(host);
	request.set_port(port);
	request.set_process_id(process_id);
	request.set_heartbeat_stream_id(heartbeat_stream_id);

	catkit_proto::testbed::RegisterServiceReply reply;

	try
	{
		reply.ParseFromString(MakeRequest("register_service", Serialize(request)));
	}
	catch (...)
	{
		throw std::runtime_error("Service could not be registered.");
	}

	return reply.state_stream_id();
}

bool TestbedProxy::IsSimulated()
{
	GetTestbedInfo();

	return m_IsSimulated;
}

bool TestbedProxy::IsAlive()
{
	GetTestbedInfo();

	auto alive_timestamp = m_HeartbeatStream->GetLatestFrame().AsArray<uint64_t>()(0);
	auto current_timestamp = GetTimeStamp();

	return (current_timestamp - alive_timestamp) < HEARTBEAT_LIVENESS * 1e9;
}

void TestbedProxy::ShutDown()
{
	catkit_proto::testbed::ShutDownRequest request;
	catkit_proto::testbed::ShutDownReply reply;

	try
	{
		reply.ParseFromString(MakeRequest("shut_down", Serialize(request)));
	}
	catch (...)
	{
		std::runtime_error("Unable to shut down Testbed.");
	}
}

std::shared_ptr<DataStream> TestbedProxy::GetHeartbeat()
{
	GetTestbedInfo();

	return m_HeartbeatStream;
}

json TestbedProxy::GetConfig()
{
	GetTestbedInfo();

	return m_Config;
}

std::string TestbedProxy::GetHost()
{
	return m_Host;
}

int TestbedProxy::GetPort()
{
	return m_Port;
}

int TestbedProxy::GetLoggingIngressPort()
{
	GetTestbedInfo();

	return m_LoggingIngressPort;
}

int TestbedProxy::GetLoggingEgressPort()
{
	GetTestbedInfo();

	return m_LoggingEgressPort;
}

int TestbedProxy::GetDataLoggingIngressPort()
{
	GetTestbedInfo();

	return m_DataLoggingIngressPort;
}

int TestbedProxy::GetDataLoggingEgressPort()
{
	GetTestbedInfo();

	return m_DataLoggingEgressPort;
}

int TestbedProxy::GetTracingIngressPort()
{
	GetTestbedInfo();

	return m_TracingIngressPort;
}

int TestbedProxy::GetTracingEgressPort()
{
	GetTestbedInfo();

	return m_TracingEgressPort;
}

std::vector<std::string> TestbedProxy::GetActiveServices()
{
	return std::vector<std::string>();
}

std::vector<std::string> TestbedProxy::GetInactiveServices()
{
	return std::vector<std::string>();
}

void TestbedProxy::GetTestbedInfo()
{
	// Do not communicate with the server unnecessarily.
	// The server info will not change over its lifetime.
	if (m_HasGottenInfo)
		return;

	catkit_proto::testbed::GetInfoRequest request;

	catkit_proto::testbed::GetInfoReply reply;
	reply.ParseFromString(MakeRequest("get_info", Serialize(request)));

	m_Config = json::parse(reply.config());
	m_IsSimulated = reply.is_simulated();

	m_HeartbeatStream = DataStream::Open(reply.heartbeat_stream_id());

	m_LoggingIngressPort = reply.logging_ingress_port();
	m_LoggingEgressPort = reply.logging_egress_port();

	m_DataLoggingIngressPort = reply.data_logging_ingress_port();
	m_DataLoggingEgressPort = reply.data_logging_egress_port();

	m_TracingIngressPort = reply.tracing_ingress_port();
	m_TracingEgressPort = reply.tracing_egress_port();

	m_HasGottenInfo = true;
}
