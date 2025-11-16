#include "ServiceProxy.h"

#include "TestbedProxy.h"
#include "Timing.h"
#include "Service.h"
#include "Util.h"
#include "service.pb.h"

#include <iostream>
#include <string>
#include <stdexcept>

using namespace std::string_literals;
using json = nlohmann::json;

const double TIMEOUT_TO_START = 120;  // seconds
const double TIMEOUT_SET_PROPERTY = 120;  // seconds
const double TIMEOUT_EXECUTE_COMMAND = 120;  // seconds

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

	// Get the value data.
	auto message = m_Testbed->GetMessageBroker()->GetCurrentMessage(m_ServiceId + "/"s + name + "/get"s);

	if (!message.has_value())
		throw std::runtime_error("Could not get the property.");

	// Decode the data.
	catkit_proto::Value proto_value;
	std::string proto_string((char *) message.value().GetPayload().data, message.value().GetPayloadSize());
	proto_value.ParseFromString(proto_string);

	Value res;
	FromProto(&proto_value, res);

	return res;
}

Value ServiceProxy::SetProperty(const std::string &name, const Value &value, void (*error_check)())
{
	// Start the service if it has not already been started.
	Start(TIMEOUT_TO_START, error_check);

	// Check if the name is a valid property.
	if (std::find(m_PropertyNames.begin(), m_PropertyNames.end(), name) == m_PropertyNames.end())
		throw std::runtime_error("This is not a valid property name.");

	std::string set_topic = m_ServiceId + "/"s + name + "/set"s;
	std::string error_topic = m_ServiceId + "/"s + name + "/error";

	// Encode value to protobuf.
	catkit_proto::Value proto_value;
	ToProto(value, &proto_value);

	std::string encoded_value;
	proto_value.SerializeToString(&encoded_value);

	// Subscribe to get messages.
	auto subscription = m_Testbed->GetMessageBroker()->Subscribe(m_ServiceId + "/"s + name, MessageSubscriptionMode::Sequential);

	// Send a set message.
	auto message = m_Testbed->GetMessageBroker()->PublishData(set_topic, encoded_value.c_str(), encoded_value.size());\
	Uuid trace_id = message.GetTraceId();

	// Wait for the response.
	Timer timer;

	while (true)
	{
		double time_remaining = TIMEOUT_SET_PROPERTY - timer.GetTime();

		if (time_remaining < 0)
			throw std::runtime_error("Timeout waiting for response");

		// Get the response message.
		auto reply_message_optional = subscription.GetNextMessage(time_remaining, EventWaitMethod::Default, error_check);

		if (!reply_message_optional.has_value())
			continue;

		auto reply_message = reply_message_optional.value();

		// Check if the message is a response to our set.
		if (reply_message.GetTraceId() != trace_id)
			continue;

		// Ignore the message we just sent.
		if (reply_message.GetTopic() == set_topic)
			continue;

		// If it's an error topic, relay the error to the caller as an exception.
		if (reply_message.GetTopic() == error_topic)
			throw std::runtime_error("Error while setting property: "s + std::string((char *) reply_message.GetPayload().data, reply_message.GetPayloadSize()));

		// Parse the response message and return the retrieved value.
		catkit_proto::Value reply;
		reply.ParseFromString(std::string((char *) reply_message.GetPayload().data, reply_message.GetPayloadSize()));

		Value res;
		FromProto(&reply, res);

		return res;
	}
}

Value ServiceProxy::ExecuteCommand(const std::string &name, const Dict &arguments, void (*error_check)())
{
	// Start the service if it has not already been started.
	Start(TIMEOUT_TO_START, error_check);

	// Check if the name is a valid command.
	if (std::find(m_CommandNames.begin(), m_CommandNames.end(), name) == m_CommandNames.end())
		throw std::runtime_error("This is not a valid command name.");

	std::string execute_topic = m_ServiceId + "/"s + name + "/execute"s;
	std::string error_topic = m_ServiceId + "/"s + name + "/error";

	catkit_proto::Dict args;
	ToProto(arguments, &args);

	// Subscribe to reply messages.
	auto subscription = m_Testbed->GetMessageBroker()->Subscribe(m_ServiceId + "/"s + name, MessageSubscriptionMode::Sequential);

	// Send the execute message.
	auto message_data = Serialize(args);
	auto message = m_Testbed->GetMessageBroker()->PublishData(execute_topic, message_data.data(), message_data.size());
	Uuid trace_id = message.GetTraceId();

	// Wait for the response.
	Timer timer;

	while (true)
	{
		double time_remaining = TIMEOUT_EXECUTE_COMMAND - timer.GetTime();

		if (time_remaining < 0)
			throw std::runtime_error("Timeout waiting for return value.");

		// Get the response message.
		auto reply_message_optional = subscription.GetNextMessage(time_remaining, EventWaitMethod::Default, error_check);

		if (!reply_message_optional.has_value())
			continue;

		auto reply_message = reply_message_optional.value();

		// Check if the message is a response to our execute message.
		if (reply_message.GetTraceId() != trace_id)
			continue;

		// Ignore the message we just sent.
		if (reply_message.GetTopic() == execute_topic)
			continue;

		// If it's an error topic, relay the error to the caller as an exception.
		if (reply_message.GetTopic() == error_topic)
			throw std::runtime_error("Error while executing command: "s + std::string((char *) reply_message.GetPayload().data, reply_message.GetPayloadSize()));

		// Parse the response message and return the retrieved value.
		catkit_proto::service::ExecuteCommandReply reply;
		reply.ParseFromString(std::string((char *) reply_message.GetPayload().data, reply_message.GetPayloadSize()));

		Value res;
		FromProto(&reply.result(), res);

		return res;
	}
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

	switch (current_state)
	{
		case ServiceState::CLOSED:
		m_Testbed->StartService(m_ServiceId);
		break;

		case ServiceState::INITIALIZING:
		case ServiceState::OPENING:
		case ServiceState::RUNNING:
		break;

		case ServiceState::CLOSING:
		throw std::runtime_error("The service is closing. Try restarting it later.");

		case ServiceState::UNRESPONSIVE:
		throw std::runtime_error("The service is unresponsive. Try reconnecting later.");

		case ServiceState::CRASHED:
		throw std::runtime_error("Refusing to start a crashed service. Ask the TestbedProxy to start it.");

		case ServiceState::FAIL_SAFE:
		throw std::runtime_error("Refusing to start a fail safed service. Ask the TestbedProxy to start it.");

		default:
		throw std::runtime_error("Unknown service state.");
	}

	// Wait for the service to actually start running.
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

			if (GetState() == ServiceState::FAIL_SAFE)
				throw std::runtime_error("The service went into fail safe during startup.");
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

	auto info_message = m_Testbed->GetMessageBroker()->GetCurrentMessage(m_ServiceId + "/info"s);

	if (!info_message.has_value())
		throw std::runtime_error("The service did not publish its info.");

	auto info_payload = info_message.value().GetPayload();
	auto info = json::parse((char *) info_payload.data, (char *) info_payload.data + info_payload.info.GetSizeInBytes());

	for (auto it : info["property_names"])
		m_PropertyNames.push_back(it);

	for (auto it : info["command_names"])
		m_CommandNames.push_back(it);

	for (auto& [key, value] : info["datastream_ids"].items())
		m_DataStreamIds[key] = value;

	m_Heartbeat = DataStream::Open(info["heartbeat_stream_id"].get<std::string>());

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
