#include "ServiceProxy.h"

#include "TestbedProxy.h"
#include "TimeStamp.h"
#include "Service.h"
#include "service.pb.h"

using namespace std::string_literals;

ServiceProxy::ServiceProxy(std::shared_ptr<TestbedProxy> testbed, std::string service_id)
	: m_Testbed(testbed), m_ServiceId(service_id)
{
	// Do a check to see if the service id is correct.
	auto testbed_config = testbed->GetConfig();

	if (!testbed_config["services"].contains(service_id))
	{
		throw std::runtime_error("Service "s + service_id + " is a non-existant service id.");
	}
}

ServiceProxy::~ServiceProxy()
{
}

Value ServiceProxy::GetProperty(const std::string &name)
{
	// Connect if we're not already connected.
	Connect();

	// Check if the name is a valid property.
	if (std::find(m_PropertyNames.begin(), m_PropertyNames.end(), name) == m_PropertyNames.end())
		throw std::runtime_error("This is not a valid property name.");

	catkit_proto::service::GetPropertyRequest request;
	request.set_property_name(name);

	std::string reply_string = m_Client->MakeRequest("get_property", Serialize(request));

	catkit_proto::service::GetPropertyReply reply;
	reply.ParseFromString(reply_string);

	Value res;
	FromProto(&reply.property_value(), res);

	return res;
}

Value ServiceProxy::SetProperty(const std::string &name, const Value &value)
{
	// Connect if we're not already connected.
	Connect();

	// Check if the name is a valid property.
	if (std::find(m_PropertyNames.begin(), m_PropertyNames.end(), name) == m_PropertyNames.end())
		throw std::runtime_error("This is not a valid property name.");

	catkit_proto::service::SetPropertyRequest request;
	request.set_property_name(name);
	ToProto(value, request.mutable_property_value());

	std::string reply_string = m_Client->MakeRequest("set_property", Serialize(request));

	catkit_proto::service::SetPropertyReply reply;
	reply.ParseFromString(reply_string);

	Value res;
	FromProto(&reply.property_value(), res);

	return res;
}

Value ServiceProxy::ExecuteCommand(const std::string &name, const Dict &arguments)
{
	// Connect if we're not already connected.
	Connect();

	// Check if the name is a valid command.
	if (std::find(m_CommandNames.begin(), m_CommandNames.end(), name) == m_CommandNames.end())
		throw std::runtime_error("This is not a valid command name.");

	catkit_proto::service::ExecuteCommandRequest request;
	request.set_command_name(name);
	ToProto(arguments, request.mutable_arguments());

	std::string reply_string = m_Client->MakeRequest("execute_command", Serialize(request));

	catkit_proto::service::ExecuteCommandReply reply;
	reply.ParseFromString(reply_string);

	Value res;
	FromProto(&reply.result(), res);

	return res;
}

std::shared_ptr<DataStream> ServiceProxy::GetDataStream(const std::string &name)
{
	// Connect if we're not already connected.
	Connect();

	// Check if the name is a valid data stream name.
	if (m_DataStreamIds.find(name) == m_DataStreamIds.end())
		throw std::runtime_error("This is not a valid data stream name.");

	auto stream = m_DataStreams.find(name);

	// Check if we already opened this data stream.
	if (stream == m_DataStreams.end())
	{
		// Open it now.
		m_DataStreams[name] = DataStream::Open(m_DataStreamIds[name]);
	}

	return m_DataStreams[name];
}

ServiceState ServiceProxy::GetState()
{
	if (m_HeartbeatStream)
	{
		// Check heartbeat stream.
		std::uint64_t heartbeat_time = m_HeartbeatStream->GetLatestFrame().AsArray<std::uint64_t>()(0);
		std::uint64_t current_time = GetTimeStamp();

		if ((current_time - heartbeat_time) / 1e9 < SERVICE_LIVELINESS)
			return ServiceState::RUNNING;
	}

	auto state = m_Testbed->GetServiceState(m_ServiceId);

	// Connect if the service became operational.
	if (m_LastKnownState != ServiceState::RUNNING && state == ServiceState::RUNNING)
		Connect();

	m_LastKnownState = state;

	return state;
}

bool ServiceProxy::IsRunning()
{
	return GetState() == ServiceState::RUNNING;
}

bool ServiceProxy::IsAlive()
{
	return IsAliveState(GetState());
}

void ServiceProxy::Start()
{
	if (IsAlive())
		return;

	m_Testbed->StartService(m_ServiceId);
}

void ServiceProxy::Stop()
{
	if (!IsAlive())
		return;

	m_Testbed->StopService(m_ServiceId);
}

void ServiceProxy::WaitUntilRunning(double timeout_in_sec, void (*error_check)())
{
	if (IsRunning())
		return;

	Start();

	Timer timer;

	while (!IsRunning())
	{
		double timeout_remaining = timeout_in_sec - timer.GetTime();

		if (timeout_remaining <= 0)
			throw std::runtime_error("Timeout has expired.");

		std::this_thread::sleep_for(std::chrono::duration<double>(std::min(double(0.05), timeout_remaining)));

		if (error_check)
			error_check();
	}
}

void ServiceProxy::Connect()
{
	// Check if we are already connected.
	if (m_Client)
		return;

	// Check if the service is running.
	if (!IsRunning())
		return;

	// Get the host and port of the service.
	auto service_info = m_Testbed->GetServiceInfo(m_ServiceId);

	// Connect to the service.
	m_Client = std::make_unique<Client>(service_info.host, service_info.port);

	// Get property, command and datastream names.
	std::string reply_string = m_Client->MakeRequest("get_info", "");

	catkit_proto::service::GetInfoReply reply;
	reply.ParseFromString(reply_string);

	m_PropertyNames.clear();
	for (auto &i : reply.property_names())
		m_PropertyNames.push_back(i);

	m_CommandNames.clear();
	for (auto &i : reply.command_names())
		m_CommandNames.push_back(i);

	for (auto& [key, value] : reply.datastream_ids())
		m_DataStreamIds[key] = value;

	m_HeartbeatStream = DataStream::Open(reply.heartbeat_stream_id());
}
