#include "Service.h"

#include "Finally.h"
#include "Timing.h"
#include "TestbedProxy.h"
#include "Tracing.h"
#include "service.pb.h"

#include <chrono>
#include <csignal>
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <zmq_addon.hpp>
#include <cstdint>
#include <string>
#include <thread>

using namespace std;
using namespace zmq;
using json = nlohmann::json;
using namespace std::string_literals;

const double SAFETY_INTERVAL = 60;  // seconds.

Service::Service(string service_type, string service_id, int service_port, int testbed_port)
	: m_Server(service_port), m_ServiceId(service_id), m_ServiceType(service_type),
	m_LoggerConsole(), m_LoggerPublish(),
	m_Heartbeat(nullptr), m_State(nullptr), m_Safety(nullptr), m_Testbed(nullptr),
	m_IsRunning(false), m_ShouldShutDown(false), m_FailSafe(false), m_IsBeingDestroyed(false)
{
	m_Testbed = make_shared<TestbedProxy>("127.0.0.1", testbed_port);
	m_Config = m_Testbed->GetConfig()["services"][service_id];

	m_LoggerPublish.Connect(service_id, "tcp://127.0.0.1:"s + to_string(m_Testbed->GetLoggingIngressPort()));

	m_Heartbeat = DataStream::Create("heartbeat", service_id, DataType::DT_UINT64, {1}, 20);

	tracing_proxy.Connect(service_id, "127.0.0.1", m_Testbed->GetTracingIngressPort());

	string state_stream_id = m_Testbed->RegisterService(
		service_id,
		service_type,
		"127.0.0.1",
		service_port,
		GetProcessId(),
		m_Heartbeat->GetStreamId()
	);

	m_State = DataStream::Open(state_stream_id);
	UpdateState(ServiceState::INITIALIZING);

	LOG_DEBUG("Registering request handlers.");

	m_Server.RegisterRequestHandler("get_info", [this](const string &data) { return this->HandleGetInfo(data); });
	m_Server.RegisterRequestHandler("execute_command", [this](const string &data) { return this->HandleExecuteCommand(data); });
	m_Server.RegisterRequestHandler("shut_down", [this](const string &data) { return this->HandleShutDown(data); });

	LOG_INFO("Intialized service.");
}

Service::~Service()
{
	// Mark that we're being destroyed to prevent any attribute access during cleanup
	m_IsBeingDestroyed = true;

	// Explicitly clean up attributes in a safe order
	// This prevents circular references from keeping the Service alive
	CleanupAttributes();
}

void Service::Run(void (*error_check)())
{
	if (m_ShouldShutDown)
		throw std::runtime_error("A service can only run once.");

	if (m_IsRunning)
		throw std::runtime_error("The service is already running.");

	// Perform check on requires safety property in config.
	if (!m_Config.contains("requires_safety"))
	{
		LOG_CRITICAL("Attribute \"requires_safety\" not found in config. This is mandatory for all services.");
		UpdateState(ServiceState::CRASHED);

		return;
	}

	// Log whether this services requires safety or not.
	if (RequiresSafety())
	{
		LOG_INFO("This service requires a safe testbed to operate.");
	}
	else
	{
		LOG_INFO("This service can operate in unsafe conditions.");
	}

	// Perform safety pre-check.
	if (!IsSafe())
	{
		LOG_CRITICAL("Testbed is unsafe. This service will not be started.");
		UpdateState(ServiceState::FAIL_SAFE);

		return;
	}

	// We can start the service now.
	LOG_INFO("Opening service.");
	UpdateState(ServiceState::OPENING);

	try
	{
		Open();
	}
	catch (std::exception &e)
	{
		LOG_CRITICAL("Something went wrong when opening service: "s + e.what());
		LOG_CRITICAL("Shutting down service.");

		m_IsRunning = false;
		UpdateState(ServiceState::CRASHED);
		return;
	}

	LOG_INFO("Service was succesfully opened.");

	// Publish all properties on startup.
	for (const auto &pair : m_Properties)
	{
		auto property_name = pair.first;
		LOG_INFO("Publishing property \""s + property_name + "\".");

		try
		{
			auto value = GetProperty(property_name);
			std::string topic = m_ServiceId + "/"s + property_name + "/get"s;
			m_Testbed->GetMessageBroker()->PublishData(topic, value.data(), value.size());
		}
		catch (std::exception &e)
		{
			std::string error_message = "Failed to get property: "s + e.what();
			LOG_ERROR(error_message);
		}
	}

	LOG_INFO("Service published all properties.");

	bool crashed = false;
	m_FailSafe = false;

	{
		// Put out an initial heartbeat.
		// This ensures that there is always a heartbeat on this channel.
		std::uint64_t timestamp = GetTimeStamp();
		m_Heartbeat->SubmitData(&timestamp);

		ArrayInfo info{'u', '=', 8, 1, {1, 1, 1, 1}, {8, 1, 1, 1}};
		m_Testbed->GetMessageBroker()->PublishArray(m_ServiceId + "/heartbeat/get", {info, &timestamp});

		// Start the safety and heartbeat threads.
		std::thread safety(&Service::MonitorSafety, this);
		std::thread heartbeat(&Service::MonitorHeartbeats, this);
		std::thread properties(&Service::MonitorProperties, this);

		// Start the server.
		m_Server.Start();

		// Ensure the server and started threads are stopped when out of this scope.
		Finally stop_server_and_monitors([this, &safety, &heartbeat, &properties]()
		{
			this->m_ShouldShutDown = true;

			this->m_Server.Stop();

			if (safety.joinable())
				safety.join();

			if (heartbeat.joinable())
				heartbeat.join();

			if (properties.joinable())
				properties.join();
		});

		// Update service state.
		m_IsRunning = true;
		UpdateState(ServiceState::RUNNING);

		LOG_INFO("Starting service main function.");

		// Start the main function.
		// The main function is called in the main thread to allow it to
		// catch KeyboardInterrupts from Python.
		try
		{
			Main();
		}
		catch (std::exception &e)
		{
			LOG_CRITICAL("Something went wrong during the main function: "s + e.what());
			LOG_CRITICAL("Shutting down service.");

			crashed = true;
		}
	}

	m_IsRunning = false;

	LOG_INFO("Service main has ended.");

	UpdateState(ServiceState::CLOSING);

	LOG_INFO("Closing service.");

	try
	{
		Close();
	}
	catch (std::exception e)
	{
		LOG_CRITICAL("Something went wrong when closing the service: "s + e.what());
	}

	if (crashed)
	{
		LOG_INFO("Service was safely closed after crash.");
		UpdateState(ServiceState::CRASHED);
	}
	else if (m_FailSafe)
	{
		LOG_INFO("Service was safely closed after safety violation.");
		UpdateState(ServiceState::FAIL_SAFE);
	}
	else
	{
		LOG_INFO("Service was closed.");
		UpdateState(ServiceState::CLOSED);
	}

	// Set heartbeat timestamp to zero to signal a dead service.
	std::uint64_t timestamp = 0;
	m_Heartbeat->SubmitData(&timestamp);

	ArrayInfo info{'u', '=', 8, 1, {1, 1, 1, 1}, {8, 1, 1, 1}};
	m_Testbed->GetMessageBroker()->PublishArray(m_ServiceId + "/heartbeat/get", {info, &timestamp});
}

void Service::CleanupAttributes()
{
	// Clear properties first - they may capture 'this' in lambdas
	// Clearing them releases those captures and breaks potential cycles
	m_Properties.clear();

	// Clear commands next - same reasoning
	m_Commands.clear();

	// Finally clear data streams - these typically don't capture 'this'
	// but clear them last to be safe
	m_DataStreams.clear();
}

void Service::MonitorSafety()
{
	while (!ShouldShutDown())
	{
		if (!IsSafe())
		{
			LOG_CRITICAL("The testbed is deemed unsafe. Shutting down.");
			m_FailSafe = true;

			ShutDown();
			return;
		}

		Sleep(SAFETY_INTERVAL);
	}
}

bool Service::IsSafe()
{
	if (!RequiresSafety())
		return true;

	try
	{
		static std::shared_ptr<ServiceProxy> safety_service(m_Testbed->GetService("safety"));

		auto stream = safety_service->GetDataStream("is_safe");
		auto frame = stream->GetLatestFrame();

		std::uint64_t current_time = GetTimeStamp();

		if ((current_time - frame.m_TimeStamp) / 1.0e9 > 3 * SAFETY_INTERVAL)
		{
			// The safety check is too old.
			// This is deemed unsafe.
			LOG_WARNING("The safety check is too old.");

			return false;
		}

		auto data = frame.AsArray<std::uint8_t>();

		if (data.sum() != data.size())
		{
			// At least one safety has failed.
			// This is deemed unsafe.
			LOG_WARNING("At least one safety check has failed.");

			return false;
		}
	}
	catch (std::exception &e)
	{
		// Something went wrong when trying to check safety.
		// This is deemed unsafe.
		LOG_ERROR("Something went wrong when checking safety: "s + e.what());

		return false;
	}

	return true;
}

bool Service::RequiresSafety()
{
	return m_Config["requires_safety"];
}

void Service::MonitorHeartbeats()
{
	while (!ShouldShutDown())
	{
		// Update my own heartbeat.
		std::uint64_t timestamp = GetTimeStamp();
		m_Heartbeat->SubmitData(&timestamp);

		ArrayInfo info{'u', '=', 8, 1, {1, 1, 1, 1}, {8, 1, 1, 1}};
		m_Testbed->GetMessageBroker()->PublishArray(m_ServiceId + "/heartbeat/get", {info, &timestamp});

		// Check the testbed heartbeat.
		if (!m_Testbed->IsAlive())
		{
			LOG_CRITICAL("Testbed has likely crashed. Shutting down.");
			ShutDown();
			return;
		}

		// Update CPU and memory usage.
		m_ProcessStats.Update();

		double cpu_usage = m_ProcessStats.GetCpuUsage();
		ArrayInfo cpu_usage_info = {'f', '=', 8, 1, {1}, {1}};
		m_Testbed->GetMessageBroker()->PublishArray(m_ServiceId + "/cpu_usage/get", {cpu_usage_info, &cpu_usage});

		uint64_t memory_usage = m_ProcessStats.GetMemoryUsage();
		ArrayInfo memory_usage_info = {'u', '=', 8, 1, {1}, {1}};
		m_Testbed->GetMessageBroker()->PublishArray(m_ServiceId + "/memory_usage/get", {memory_usage_info, &memory_usage});

		// Sleep until next check.
		Sleep(SERVICE_LIVELINESS / 5);
	}
}

void Service::MonitorProperties()
{
	auto broker = m_Testbed->GetMessageBroker();
	auto subscription = broker->Subscribe(m_ServiceId);

	while (!ShouldShutDown())
	{
		try
		{
			auto message_optional = subscription.GetNextMessage(SERVICE_LIVELINESS / 5, EventWaitMethod::Default);

			if (!message_optional.has_value())
				continue;

			auto message = message_optional.value();
			auto topic = message.GetTopic();

			// Only trigger on set messages.
			if (topic.substr(topic.size() - 4) != "/set")
				continue;

			std::string get_topic = std::string(topic.substr(0, topic.size() - 4)) + "/get"s;
			std::string error_topic = std::string(topic.substr(0, topic.size() - 4)) + "/error"s;

			// Find the property name. The topic is "<service_id>/<property_name>/set".
			std::string property_name = std::string(topic.substr(m_ServiceId.size() + 1, topic.size()- m_ServiceId.size() - 5));

			// Find the property. If a property by that name doesn't exist, ignore the message.
			auto property = m_Properties.find(property_name);
			if (property == m_Properties.end())
				continue;

			try
			{
				// Set the property value.
				SetProperty(property_name, std::string_view((char *)message.GetPayload().data, message.GetPayloadSize()));
			}
			catch (const std::exception& e)
			{
				std::string error_message = "Failed to set property: "s + e.what();
				LOG_ERROR(error_message);

				broker->PublishData(error_topic, error_message.data(), error_message.size(), message.GetTraceId());
				continue;
			}

			try
			{
				// Publish the new property value;
				auto new_property_value = GetProperty(property_name);

				broker->PublishData(get_topic, new_property_value.data(), new_property_value.size(), message.GetTraceId());
			}
			catch (const std::exception& e)
			{
				std::string error_message = "Failed to get property: "s + e.what();
				LOG_ERROR(error_message);

				broker->PublishData(error_topic, error_message.data(), error_message.size(), message.GetTraceId());
				continue;
			}
		}
		catch (const std::exception& e)
		{
			continue;
		}
	}
}

void Service::Open()
{
}

void Service::Main()
{
	LOG_CRITICAL("You MUST override the main() function for correct service behaviour.");
}

void Service::Close()
{
}

void Service::ShutDown()
{
	m_ShouldShutDown = true;
}

bool Service::ShouldShutDown()
{
	return m_ShouldShutDown;
}

bool Service::IsRunning()
{
	return m_IsRunning;
}

void Service::Sleep(double sleep_time_in_sec, void (*error_check)())
{
	::Sleep(sleep_time_in_sec, [this, error_check]()
	{
		if (error_check)
			error_check();

		return this->ShouldShutDown();
	});
}

std::shared_ptr<Command> Service::GetCommand(const std::string &command_name) const
{
	auto i = m_Commands.find(command_name);

	if (i != m_Commands.end())
		return i->second;
	else
		return nullptr;
}

std::shared_ptr<DataStream> Service::GetDataStream(const std::string &stream_name) const
{
	auto i = m_DataStreams.find(stream_name);

	if (i != m_DataStreams.end())
		return i->second;
	else
		return nullptr;
}

json Service::GetConfig() const
{
	return m_Config;
}

const std::string &Service::GetId() const
{
	return m_ServiceId;
}

void Service::MakeProperty(std::string property_name, PropertyGetter getter, PropertySetter setter)
{
	LOG_DEBUG("Making property \"" + property_name + "\".");

	m_Properties[property_name] = {getter, setter};
}



void Service::MakeCommand(std::string command_name, Command::CommandFunction func)
{
	LOG_DEBUG("Making command \"" + command_name + "\".");

	auto cmd = std::make_shared<Command>(command_name, func);
	m_Commands[command_name] = cmd;
}



std::shared_ptr<DataStream> Service::MakeDataStream(std::string stream_name, DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer)
{
	LOG_DEBUG("Making data stream \"" + stream_name + "\".");

	std::shared_ptr<DataStream> stream = DataStream::Create(stream_name, GetId(), type, dimensions, num_frames_in_buffer);
	m_DataStreams[stream_name] = stream;

	return stream;
}

std::shared_ptr<DataStream> Service::ReuseDataStream(std::string stream_name, std::string stream_id)
{
	LOG_DEBUG("Reusing data stream \"" + stream_name + "\".");

	std::shared_ptr<DataStream> stream = DataStream::Open(stream_id);
	m_DataStreams[stream_name] = stream;

	return stream;
}

std::shared_ptr<TestbedProxy> Service::GetTestbed()
{
	return m_Testbed;
}

std::string Service::GetProperty(std::string property_name)
{
	if (m_IsBeingDestroyed)
		throw std::runtime_error("Cannot access property \"" + property_name + "\" while service is being destroyed.");

	auto i = m_Properties.find(property_name);

	if (i == m_Properties.end())
		throw std::runtime_error("Property \"" + property_name + "\" does not exist.");

	PropertyGetter getter = i->second.first;
	if (getter == nullptr)
		throw std::runtime_error("Property \"" + property_name + "\" cannot be read from.");

	Value value = getter();

	// Convert the value to a buffer.
	catkit_proto::Value proto_value;
	ToProto(value, &proto_value);

	std::string serialized;
	proto_value.SerializeToString(&serialized);

	return serialized;
}

void Service::SetProperty(std::string property_name, std::string_view value)
{
	if (m_IsBeingDestroyed)
		throw std::runtime_error("Cannot set property \"" + property_name + "\" while service is being destroyed.");

	auto i = m_Properties.find(property_name);

	if (i == m_Properties.end())
		throw std::runtime_error("Property \"" + property_name + "\" does not exist.");

	PropertySetter setter = i->second.second;
	if (setter == nullptr)
		throw std::runtime_error("Property \"" + property_name + "\" cannot be written to.");

	// Convert the value from a buffer.
	catkit_proto::Value proto_value;
	proto_value.ParseFromArray(value.data(), value.size());

	Value val;
	FromProto(&proto_value, val);

	// Call the setter.
	setter(val);
}

string Service::HandleGetInfo(const string &data)
{
	// There's no data in the request, so don't even parse it.
	// Create the reply protobuffer object.
	catkit_proto::service::GetInfoReply reply;

	reply.set_service_id(m_ServiceId);
	reply.set_service_type(m_ServiceType);
	reply.set_config(m_Config.dump());

	for (auto& [key, value] : m_Properties)
		reply.add_property_names(key);

	for (auto& [key, value] : m_Commands)
		reply.add_command_names(key);

	for (auto& [key, value] : m_DataStreams)
		(*reply.mutable_datastream_ids())[key] = value->GetStreamId();

	reply.set_heartbeat_stream_id(m_Heartbeat->GetStreamId());

	std::string reply_string;
	reply.SerializeToString(&reply_string);

	return reply_string;
}

string Service::HandleExecuteCommand(const string &data)
{
	catkit_proto::service::ExecuteCommandRequest request;
	request.ParseFromString(data);

	std::string command_name = request.command_name();
	auto command = GetCommand(command_name);

	if (!command)
		throw std::runtime_error("Command \""s + command_name + "\" does not exist.");

	Dict args;
	FromProto(&request.arguments(), args);
	auto res = command->Execute(args);

	catkit_proto::service::ExecuteCommandReply reply;
	ToProto(res, reply.mutable_result());

	string reply_string;
	reply.SerializeToString(&reply_string);

	return reply_string;
}

string Service::HandleShutDown(const string &data)
{
	ShutDown();

	catkit_proto::service::ShutDownReply reply;

	string reply_string;
	reply.SerializeToString(&reply_string);

	return reply_string;
}

void Service::UpdateState(ServiceState state)
{
	int8_t new_state = state;
	m_State->SubmitData(&new_state);
}

void print_usage()
{
	std::cout
		<< "Usage:" << std::endl
		<< "service --id=ID --port=PORT --testbed_port=TESTBED_PORT" << std::endl
		<< std::endl
		<< "Options:" << std::endl
		<< "--id=ID                      The ID of the service. This should correspond to a value in the testbed configuration." << std::endl
		<< "--port=PORT                  The port for this service." << std::endl
		<< "--testbed_port=TESTBED_PORT  The port where the testbed is running." << std::endl;
}

std::tuple<std::string, int, int> ParseServiceArgs(std::vector<std::string> arguments)
{
	std::string service_id;
	int service_port;
	int testbed_port;

	bool id_found = false;
	bool service_port_found = false;
	bool testbed_port_found = false;

	size_t i = 1;
	while (i < arguments.size())
	{
		std::string arg = arguments[i];

		if (arg == "--id" || arg == "-n")
		{
			if (i + 1 == arguments.size())
			{
				print_usage();
				throw std::runtime_error("Did not supply all arguments.");
			}

			service_id = arguments[i + 1];
			id_found = true;

			i += 2;
		}
		else if (arg.rfind("--id=", 0) == 0)
		{
			service_id = arg.substr(5);  // 5 is the length of "--id=".
			id_found = true;

			i += 1;
		}
		else if (arg.rfind("-n=", 0) == 0)
		{
			service_id = arg.substr(3);
			id_found = true;

			i += 1;
		}
		else if (arg == "--port" || arg == "-p")
		{
			if (i + 1 == arguments.size())
			{
				print_usage();
				throw std::runtime_error("Did not supply all arguments.");
			}

			service_port = std::stoi(arguments[i + 1]);
			service_port_found = true;

			i += 2;
		}
		else if (arg.rfind("--port=", 0) == 0)
		{
			service_port = std::stoi(arg.substr(7));  // 7 is the length of "--port=".
			service_port_found = true;

			i += 1;
		}
		else if (arg.rfind("-p=", 0) == 0)
		{
			service_port = std::stoi(arg.substr(3));
			service_port_found = true;

			i += 1;
		}
		else if (arg == "--testbed_port" || arg == "-t")
		{
			if (i + 1 == arguments.size())
			{
				print_usage();
				throw std::runtime_error("Did not supply all arguments.");
			}

			testbed_port = std::stoi(arguments[i + 1]);
			testbed_port_found = true;

			i += 2;
		}
		else if (arg.rfind("--testbed_port=", 0) == 0)
		{
			testbed_port = std::stoi(arg.substr(15));  // 15 is the length of "--testbed_port=".
			testbed_port_found = true;

			i += 1;
		}
		else if (arg.rfind("-t=", 0) == 0)
		{
			testbed_port = std::stoi(arg.substr(3));
			testbed_port_found = true;

			i += 1;
		}
		else
		{
			print_usage();
			throw std::runtime_error(std::string("Invalid argument '") + arg);
		}
	}

	if (!(id_found && service_port_found && testbed_port_found))
	{
		print_usage();
		throw std::runtime_error("Did not supply all arguments.");
	}

	// Due to different types of service ids and ports, this cannot be a std::map<key, value>
	// and has to be a tuple, which supports different data types.
	return std::make_tuple(service_id, service_port, testbed_port);
}
