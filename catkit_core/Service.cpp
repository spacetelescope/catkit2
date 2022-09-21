#include "Service.h"

#include "Finally.h"
#include "Timing.h"
#include "TestbedProxy.h"
#include "proto/service.pb.h"

#include <chrono>
#include <csignal>
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <zmq_addon.hpp>

using namespace std;
using namespace zmq;
using json = nlohmann::json;
using namespace std::string_literals;

const double SAFETY_INTERVAL = 60;  // seconds.

Service::Service(string service_type, string service_id, int service_port, int testbed_port)
	: m_Server(service_port), m_ServiceId(service_id), m_ServiceType(service_type),
	m_LoggerConsole(), m_LoggerPublish(service_id, "tcp://127.0.0.1:"s + to_string(testbed_port + 1)),
	m_Heartbeat(nullptr), m_State(nullptr), m_Safety(nullptr), m_Testbed(nullptr),
	m_IsRunning(false), m_ShouldShutDown(false), m_FailSafe(false)
{
	m_Testbed = make_shared<TestbedProxy>("127.0.0.1", testbed_port);
	m_Config = m_Testbed->GetConfig()["services"][service_id];

	m_Heartbeat = DataStream::Create("heartbeat", service_id, DataType::DT_UINT64, {1}, 20);

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
	m_Server.RegisterRequestHandler("get_property", [this](const string &data) { return this->HandleGetProperty(data); });
	m_Server.RegisterRequestHandler("set_property", [this](const string &data) { return this->HandleSetProperty(data); });
	m_Server.RegisterRequestHandler("execute_command", [this](const string &data) { return this->HandleExecuteCommand(data); });
	m_Server.RegisterRequestHandler("shut_down", [this](const string &data) { return this->HandleShutDown(data); });

	LOG_INFO("Intialized service.");
}

Service::~Service()
{
}

void Service::Run(void (*error_check)())
{
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
		UpdateState(ServiceState::CRASHED);

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

	bool crashed = false;
	m_FailSafe = false;

	{
		// Put out an initial heartbeat.
		// This ensures that there is always a heartbeat on this channel.
		std::uint64_t timestamp = GetTimeStamp();
		m_Heartbeat->SubmitData(&timestamp);

		// Start the safety and heartbeat threads.
		std::thread safety(&Service::MonitorSafety, this);
		std::thread heartbeat(&Service::MonitorHeartbeats, this);

		// Start the server.
		m_Server.Start();

		// Ensure the server and started threads are stopped when out of this scope.
		Finally stop_server_and_monitors([this, &safety, &heartbeat]()
		{
			this->m_ShouldShutDown = true;

			this->m_Server.Stop();

			if (safety.joinable())
				safety.join();

			if (heartbeat.joinable())
				heartbeat.join();
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
		UpdateState(ServiceState::CRASHED);
	}
	else
	{
		LOG_INFO("Service was closed.");
		UpdateState(ServiceState::CLOSED);
	}

	// Set heartbeat timestamp to zero to signal a dead service.
	std::uint64_t timestamp = 0;
	m_Heartbeat->SubmitData(&timestamp);
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

		// Check the testbed heartbeat.
		if (!m_Testbed->IsAlive())
		{
			LOG_CRITICAL("Testbed has likely crashed. Shutting down.");
			ShutDown();
			return;
		}

		// Sleep until next check.
		Sleep(SERVICE_LIVELINESS / 5);
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

std::shared_ptr<Property> Service::GetProperty(const std::string &property_name) const
{
	auto i = m_Properties.find(property_name);

	if (i != m_Properties.end())
		return i->second;
	else
		return nullptr;
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

void Service::MakeProperty(std::string property_name, Property::Getter getter, Property::Setter setter)
{
	LOG_DEBUG("Making property \"" + property_name + "\".");

	auto prop = std::make_shared<Property>(property_name, getter, setter);
	m_Properties[property_name] = prop;
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

	auto stream = DataStream::Create(stream_name, GetId(), type, dimensions, num_frames_in_buffer);
	m_DataStreams[stream_name] = stream;

	return stream;
}

std::shared_ptr<DataStream> Service::ReuseDataStream(std::string stream_name, std::string stream_id)
{
	LOG_DEBUG("Reusing data stream \"" + stream_name + "\".");

	auto stream = DataStream::Open(stream_id);
	m_DataStreams[stream_name] = stream;

	return stream;
}

std::shared_ptr<TestbedProxy> Service::GetTestbed()
{
	return m_Testbed;
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

string Service::HandleGetProperty(const string &data)
{
	catkit_proto::service::GetPropertyRequest request;
	request.ParseFromString(data);

	std::string property_name = request.property_name();
	auto property = GetProperty(property_name);

	if (!property)
		throw std::runtime_error("Property \""s + property_name + "\" does not exist.");

	auto value = property->Get();

	catkit_proto::service::GetPropertyReply reply;
	ToProto(value, reply.mutable_property_value());

	string reply_string;
	reply.SerializeToString(&reply_string);

	return reply_string;
}

string Service::HandleSetProperty(const string &data)
{
	catkit_proto::service::SetPropertyRequest request;
	request.ParseFromString(data);

	std::string property_name = request.property_name();
	auto property = GetProperty(property_name);

	if (!property)
		throw std::runtime_error("Property \""s + property_name + "\" does not exist.");

	Value set_value;
	FromProto(&request.property_value(), set_value);
	property->Set(set_value);

	auto value = property->Get();

	catkit_proto::service::SetPropertyReply reply;
	ToProto(value, reply.mutable_property_value());

	string reply_string;
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
	std::cout << "Usage:\n  service --id ID --port PORT --testbed_port TESTBEDPORT";
}

std::tuple<std::string, int, int> ParseServiceArgs(int argc, char *argv[])
{
	if (argc != 7)
	{
		print_usage();
		throw std::runtime_error("Too few or too many arguments.");
	}

	std::string service_id;
	int service_port;
	int testbed_port;

	bool id_found = false;
	bool service_port_found = false;
	bool testbed_port_found = false;

	for (size_t i = 1; i < argc; i += 2)
	{
		std::string arg = argv[i];
		std::string param = argv[i + 1];

		if (arg == "--id" || arg == "-n")
		{
			service_id = param;
			id_found = true;
		}
		else if (arg == "--port" || arg == "-p")
		{
			service_port = std::stoi(param);
			service_port_found = true;
		}
		else if (arg == "--testbed_port" || arg == "-t")
		{
			testbed_port = std::stoi(param);
			testbed_port_found = true;
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

	return std::make_tuple(service_id, service_port, testbed_port);
}
