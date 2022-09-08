#include "ServiceProxy.h"

#include "TestbedProxy.h"
#include "Timing.h"
#include "Service.h"
#include "Util.h"
#include "proto/service.pb.h"

#include <iostream>

using namespace std::string_literals;

const double TIMEOUT_TO_START = 30;  // seconds

ServiceProxy::ServiceProxy(std::shared_ptr<TestbedProxy> testbed, std::string service_id)
	: m_Testbed(testbed), m_ServiceId(service_id), m_Client(nullptr), m_State(nullptr),
	m_TimeLastConnect(0)
{
	// Do a check to see if the service id is correct.
	auto testbed_config = testbed->GetConfig();

	if (!testbed_config["services"].contains(service_id))
	{
		throw std::runtime_error("Service "s + service_id + " is a nonexistent service id.");
	}

	auto service_info = testbed->GetServiceInfo(m_ServiceId);

	m_State = DataStream::Open(service_info.state_stream_id);

	Connect();
}

ServiceProxy::~ServiceProxy()
{
}

Value ServiceProxy::GetProperty(const std::string &name, void (*error_check)())
{
	// Start the service if it has not already been started.
	Start(TIMEOUT_TO_START, error_check);

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

Value ServiceProxy::SetProperty(const std::string &name, const Value &value, void (*error_check)())
{
	// Start the service if it has not already been started.
	Start(TIMEOUT_TO_START, error_check);

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

Value ServiceProxy::ExecuteCommand(const std::string &name, const Dict &arguments, void (*error_check)())
{
	// Start the service if it has not already been started.
	Start(TIMEOUT_TO_START, error_check);

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

std::shared_ptr<DataStream> ServiceProxy::GetDataStream(const std::string &name, void (*error_check)())
{
	// Start the service if it has not already been started.
	Start(TIMEOUT_TO_START, error_check);

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

std::shared_ptr<DataStream> ServiceProxy::GetHeartbeat()
{
	return m_Heartbeat;
}

ServiceState ServiceProxy::GetState()
{
	ServiceState state = ServiceState(m_State->GetLatestFrame().AsArray<std::int8_t>()(0));

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

void ServiceProxy::Start(double timeout_in_sec, void (*error_check)())
{
	auto current_state = GetState();

	// Start the service if it's not already alive.
	if (current_state == ServiceState::CLOSED)
	{
		m_Testbed->StartService(m_ServiceId);
	}

	if (current_state == ServiceState::CRASHED)
		throw std::runtime_error("Refusing to start a crashed service. Use the TestbedProxy to start it.");

	// TODO: what should we do when the service is closing?

	// Wait for the service to actually start.
	if (timeout_in_sec > 0)
	{
		Timer timer;

		while (!IsRunning())
		{
			double timeout_remaining = timeout_in_sec - timer.GetTime();

			if (timeout_remaining <= 0)
				throw std::runtime_error("The service has not started within the timeout time.");

			std::this_thread::sleep_for(std::chrono::duration<double>(std::min(double(0.001), timeout_remaining)));

			if (error_check)
				error_check();

			if (GetState() == ServiceState::CRASHED)
				throw std::runtime_error("The service crashed during startup.");
		}
	}

	// Connect to the service.
	Connect();
}

void ServiceProxy::Stop()
{
	if (!IsRunning())
		return;

	Connect();

	catkit_proto::service::ShutDownRequest request;

	try
	{
		m_Client->MakeRequest("shut_down", Serialize(request));
	}
	catch (...)
	{
		throw std::runtime_error("Unable to stop service.");
	}
}

void ServiceProxy::Interrupt()
{
	if (!IsAlive())
		return;

	m_Testbed->InterruptService(m_ServiceId);
}

void ServiceProxy::Terminate()
{
	if (!IsAlive())
		return;

	m_Testbed->TerminateService(m_ServiceId);
}

void ServiceProxy::Connect()
{
	// Check if the service is running.
	// Do an explicit check on the state stream to avoid infinite loop.
	auto frame = m_State->GetLatestFrame();
	ServiceState state = ServiceState(frame.AsArray<std::int8_t>()(0));

	if (state != ServiceState::RUNNING)
	{
		// Disconnect.
		Disconnect();
		return;
	}

	// Check if we are already connected to the Service.
	if (m_TimeLastConnect == frame.m_TimeStamp)
		return;

	// We need to reconnect, so let's disconnect first.
	Disconnect();

	// Get the host and port of the service.
	auto service_info = m_Testbed->GetServiceInfo(m_ServiceId);

	// Connect to the service.
	m_Client = std::make_unique<Client>(service_info.host, service_info.port);

	// Get property, command and datastream names.
	std::string reply_string = m_Client->MakeRequest("get_info", "");

	catkit_proto::service::GetInfoReply reply;
	reply.ParseFromString(reply_string);

	for (auto &i : reply.property_names())
		m_PropertyNames.push_back(i);

	for (auto &i : reply.command_names())
		m_CommandNames.push_back(i);

	for (auto& [key, value] : reply.datastream_ids())
		m_DataStreamIds[key] = value;

	m_Heartbeat = DataStream::Open(reply.heartbeat_stream_id());

	m_TimeLastConnect = frame.m_TimeStamp;
	LOG_DEBUG("Connected to \"" + m_ServiceId + "\".");
}

void ServiceProxy::Disconnect()
{
	m_Client = nullptr;
	m_PropertyNames.clear();
	m_CommandNames.clear();
	m_DataStreamIds.clear();
	m_DataStreams.clear();

	m_Heartbeat = nullptr;
}

std::vector<std::string> ServiceProxy::GetPropertyNames(void (*error_check)())
{
	// Start the service if it has not already been started.
	Start(TIMEOUT_TO_START, error_check);

	return m_PropertyNames;
}

std::vector<std::string> ServiceProxy::GetCommandNames(void (*error_check)())
{
	// Start the service if it has not already been started.
	Start(TIMEOUT_TO_START, error_check);

	return m_CommandNames;
}

std::vector<std::string> ServiceProxy::GetDataStreamNames(void (*error_check)())
{
	// Start the service if it has not already been started.
	Start(TIMEOUT_TO_START, error_check);

	std::vector<std::string> names;

	for (auto const &item : m_DataStreamIds)
		names.push_back(item.first);

	return names;
}

nlohmann::json ServiceProxy::GetConfig()
{
	return m_Testbed->GetConfig()["services"][m_ServiceId];
}

std::string ServiceProxy::GetId()
{
	return m_ServiceId;
}

std::shared_ptr<TestbedProxy> ServiceProxy::GetTestbed()
{
	return m_Testbed;
}
