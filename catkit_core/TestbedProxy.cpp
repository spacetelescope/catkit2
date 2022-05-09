#include "TestbedProxy.h"

#include "server.pb.h"

using namespace std;
using namespace zmq;
using json = nlohmann::json;
using namespace std::string_literals;

TestbedProxy::TestbedProxy(std::string host, int port)
	: Client(host, port), m_HasGottenInfo(false)
{
	// TODO: Maybe to a check early on to see if something is listening on this port.
}

TestbedProxy::~TestbedProxy()
{
}

std::shared_ptr<ServiceProxy> TestbedProxy::GetService(const std::string &service_id)
{

}

void TestbedProxy::RequireService(const std::string &service_id)
{
	catkit_proto::RequireServiceRequest request;
	request.set_service_id(service_id);

	catkit_proto::RequireServiceReply reply;

	try
	{
		MakeRequest("require_service", request, reply);
	}
	catch
	{
		throw std::runtime_error("Unable to require service.");
	}
}

void TestbedProxy::RequireServices(std::vector<std::string> service_ids)
{
	for (const std::string &service_id : service_ids)
		RequireService(service_id);
}

ServiceState GetServiceState(const std::string &service_id)
{
	catkit_proto::GetServiceInfoRequest request;
	request.set_service_id(service_id);

	catkit_proto::GetServiceInfoReply reply;

	try
	{
		MakeRequest("get_service_info", request, reply);
	}
	catch
	{
		throw std::runtime_error("Unable to get service info.");
	}

	return reply.service_state();
}

void TestbedProxy::RegisterService(std::string service_id, std::string service_type, int port)
{
	catkit_proto::RegisterServiceRequest request;
	request.set_service_id(service_id);
	request.set_service_type(service_type);
	request.set_host("127.0.0.1");
	request.set_port(port);

	catkit_proto::RegisterServiceReply reply;

	try
	{
		MakeRequest("register_service", request, reply);
	}
	catch
	{
		std::runtime_error("Service could not be registered.");
	}

	m_Config = json::parse(reply.service_config());
}

void TestbedProxy::UpdateServiceState(std::string service_id, ServiceState new_state)
{
	catkit_proto::UpdateServiceStateRequest request;
	request.set_service_id(service_id);
	request.set_new_state(new_state);

	catkit_proto::UpdateServiceStateReply reply;

	try
	{
		MakeRequest("update_service_state", request, reply);
	}
	catch
	{
		std::runtime_error("Service state could not be updated.");
	}
}

bool TestbedProxy::IsSimulated()
{
	GetServerInfo();

	return m_IsSimulated;
}

bool TestbedProxy::IsAlive()
{
	GetServerInfo();

	// TODO: check heartbeat stream.
}

std::string TestbedProxy::GetExperimentPath()
{
}

std::string TestbedProxy::StartNewExperiment(std::string experiment_name, json metadata)
{
}

json TestbedProxy::GetConfig()
{
	GetServerInfo();

	return m_Config;
}

std::string TestbedProxy::GetHost()
{
	return m_Host;
}

int TestbedProxy::GetLoggingEgressPort()
{
	return m_LoggingEgressPort;
}

int TestbedProxy::GetTracingIngressPort()
{
	return m_TracingIngressPort;
}

std::vector<std::string> TestbedProxy::GetActiveServices()
{
}

std::vector<std::string> TestbedProxy::GetInactiveServices()
{
}

void TestbedProxy::GetServerInfo()
{
	// Do not communicate with the server unnecessarily.
	// The server info will not change over its lifetime.
	if (m_HasGottenInfo)
		return;

	catkit_proto::ServerInfoRequest request;

	catkit_proto::ServerInfoReply reply;
	MakeRequest("get_server_info", request, reply);

	m_Config = json::parse(reply.config());
	m_IsSimulated = reply.is_simulated();

	m_HeartbeatStream = DataStream::Open(reply.heartbeat_stream_id());

	m_LoggingIngressPort = reply.logging_ingress_port();
	m_LoggingEgressPort = reply.logging_egress_port();
	m_DataLoggingIngressPort = reply.data_logging_ingress_port();
	m_TracingIngressPort = reply.tracing_ingress_port();

	m_HasGottenInfo = true;
}
