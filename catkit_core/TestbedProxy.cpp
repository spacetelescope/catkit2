#include "TestbedProxy.h"

#include "testbed.pb.h"

#include <memory>

using namespace std;
using namespace zmq;
using json = nlohmann::json;
using namespace std::string_literals;

const double HEARTBEAT_LIVENESS = 30;

TestbedProxy::TestbedProxy(std::string host, int port)
	: Client(host, port), m_Host(host), m_HasGottenInfo(false)
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

void TestbedProxy::RequireService(const std::string &service_id)
{
	catkit_proto::testbed::RequireServiceRequest request;
	request.set_service_id(service_id);

	catkit_proto::testbed::RequireServiceReply reply;

	try
	{
		MakeRequest("require_service", request, reply);
	}
	catch (...)
	{
		throw std::runtime_error("Unable to require service.");
	}
}

void TestbedProxy::RequireServices(std::vector<std::string> service_ids)
{
	for (const std::string &service_id : service_ids)
		RequireService(service_id);
}

ServiceReference TestbedProxy::GetServiceInfo(const std::string &service_id)
{
	catkit_proto::testbed::GetServiceInfoRequest request;
	request.set_service_id(service_id);

	catkit_proto::testbed::GetServiceInfoReply reply;

	try
	{
		MakeRequest("get_service_info", request, reply);
	}
	catch (...)
	{
		throw std::runtime_error("Unable to get service info.");
	}

	ServiceReference res;

	res.id = reply.service().id();
	res.type = reply.service().type();
	res.state = reply.service().state();
	res.host = reply.service().host();
	res.port = reply.service().port();

	return res;
}

ServiceState TestbedProxy::GetServiceState(const std::string &service_id)
{
	return GetServiceInfo(service_id).state;
}

void TestbedProxy::RegisterService(std::string service_id, std::string service_type, int port)
{
	catkit_proto::testbed::RegisterServiceRequest request;
	request.set_service_id(service_id);
	request.set_service_type(service_type);
	request.set_host("127.0.0.1");
	request.set_port(port);

	catkit_proto::testbed::RegisterServiceReply reply;

	try
	{
		MakeRequest("register_service", request, reply);
	}
	catch (...)
	{
		std::runtime_error("Service could not be registered.");
	}

	m_Config = json::parse(reply.service_config());
}

void TestbedProxy::UpdateServiceState(std::string service_id, ServiceState new_state)
{
	catkit_proto::testbed::UpdateServiceStateRequest request;
	request.set_service_id(service_id);
	request.set_new_state(new_state);

	catkit_proto::testbed::UpdateServiceStateReply reply;

	try
	{
		MakeRequest("update_service_state", request, reply);
	}
	catch (...)
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
	auto alive_timestamp = m_HeartbeatStream->GetLatestFrame().AsArray<uint64_t>()(0);
	auto current_timestamp = GetTimeStamp();

	return (current_timestamp - alive_timestamp) < HEARTBEAT_LIVENESS * 1e9;
}

std::string TestbedProxy::GetExperimentPath()
{
	catkit_proto::testbed::GetExperimentPathRequest request;
	catkit_proto::testbed::GetExperimentPathReply reply;

	try
	{
		MakeRequest("get_experiment_path", request, reply);
	}
	catch (...)
	{
		throw std::runtime_error("Could not get the experiment path.");
	}

	return reply.experiment_path();
}

std::string TestbedProxy::StartNewExperiment(std::string experiment_name, json metadata)
{
	catkit_proto::testbed::StartNewExperimentRequest request;
	request.set_experiment_name(experiment_name);
	request.set_metadata(metadata.dump());

	catkit_proto::testbed::StartNewExperimentReply reply;
	try
	{
		MakeRequest("start_new_experiment", request, reply);
	}
	catch (...)
	{
		throw std::runtime_error("Could not start a new experiment.");
	}

	return reply.experiment_path();
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
	return std::vector<std::string>();
}

std::vector<std::string> TestbedProxy::GetInactiveServices()
{
	return std::vector<std::string>();
}

void TestbedProxy::GetServerInfo()
{
	// Do not communicate with the server unnecessarily.
	// The server info will not change over its lifetime.
	if (m_HasGottenInfo)
		return;

	catkit_proto::testbed::GetInfoRequest request;

	catkit_proto::testbed::GetInfoReply reply;
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
