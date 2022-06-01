#include "Service.h"

#include "TimeStamp.h"
#include "TestbedProxy.h"
#include "service.pb.h"

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

const double SAFETY_INTERVAL = 60;

class Finally
{
public:
	Finally(std::function<void()> func)
		: m_Func(func)
	{
	}

	~Finally()
	{
		m_Func();
	}

private:
	std::function<void()> m_Func;
};

Service::Service(string service_id, string service_type, int service_port, int testbed_port)
	: Server(service_port),
	m_ServiceId(service_id), m_ServiceType(service_type),
	m_LoggerConsole(), m_LoggerPublish(service_id, "tcp://127.0.0.1:"s + to_string(testbed_port + 1))
{
	m_Testbed = make_shared<TestbedProxy>("127.0.0.1", testbed_port);
	m_Config = m_Testbed->GetConfig()["services"][service_id];

	m_Testbed->UpdateServiceState(service_id, ServiceState::INITIALIZING);
}

Service::~Service()
{
}

void Service::Run()
{
	if (!IsSafe())
	{
		LOG_CRITICAL("Testbed is unsafe. This service will not be started.");
		return;
	}

	LOG_INFO("Opening service.");

	m_Testbed->UpdateServiceState(m_ServiceId, ServiceState::OPENING);

	try
	{
		Open();
	}
	catch (std::exception &e)
	{
		LOG_CRITICAL("Something went wrong when opening service: "s + e.what());
		LOG_CRITICAL("Shutting down service.");

		m_Testbed->UpdateServiceState(m_ServiceId, ServiceState::CRASHED);
		return;
	}

	LOG_INFO("Service was succesfully opened.");

	m_Testbed->UpdateServiceState(m_ServiceId, ServiceState::OPERATIONAL);

	LOG_INFO("Starting service main function.");

	{
		std::thread main([this]()
		{
			Finally stop_service([this]()
			{
				this->ShutDown();
			});

			try
			{
				this->Main();
			}
			catch (std::exception &e)
			{
				LOG_CRITICAL("Something went wrong during the main function: "s + e.what());
				LOG_CRITICAL("Shutting down service.");
			}
		});

		std::thread safety(&Service::MonitorSafety, this);

		Finally end_threads([&, this]()
		{
			this->ShutDown();

			if (main.joinable())
				main.join();

			if (safety.joinable())
				safety.join();
		});

		RunServer();
	}

	LOG_INFO("Service main has ended.");

	m_Testbed->UpdateServiceState(m_ServiceId, ServiceState::CLOSING);

	LOG_INFO("Closing service.");

	try
	{
		Close();
	}
	catch (std::exception e)
	{
		LOG_CRITICAL("Something went wrong when closing the service: "s + e.what());
	}

	LOG_INFO("Service was closed.");

	m_Testbed->UpdateServiceState(m_ServiceId, ServiceState::CLOSED);
}

void Service::MonitorSafety()
{
	while (!m_ShouldShutDown)
	{
		if (!IsSafe())
		{
			ShutDown();
			return;
		}

		Sleep(SAFETY_INTERVAL);
	}
}

bool Service::IsSafe()
{
	return true;
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

std::shared_ptr<Property> Service::MakeProperty(std::string property_name, Property::Getter getter, Property::Setter setter)
{
	auto prop = std::make_shared<Property>(property_name, getter, setter);
	m_Properties[property_name] = prop;

	return prop;
}

std::shared_ptr<Command> Service::MakeCommand(std::string command_name, Command::CommandFunction func)
{
	auto cmd = std::make_shared<Command>(command_name, func);
	m_Commands[command_name] = cmd;

	return cmd;
}

std::shared_ptr<DataStream> Service::MakeDataStream(std::string stream_name, DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer)
{
	auto stream = DataStream::Create(stream_name, GetId(), type, dimensions, num_frames_in_buffer);
	m_DataStreams[stream_name] = stream;

	return stream;
}

std::shared_ptr<DataStream> Service::ReuseDataStream(std::string stream_name, std::string stream_id)
{
	auto stream = DataStream::Open(stream_id);
	m_DataStreams[stream_name] = stream;

	return stream;
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
		reply.add_property_names(key);

	auto map = reply.datastream_ids();

	for (auto& [key, value] : m_DataStreams)
		map[key] = value->GetStreamId();

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

void print_usage()
{
	std::cout << "Usage:\n  service --name NAME --port PORT";
}

std::tuple<std::string, int, int> ParseServiceArgs(int argc, char *argv[])
{
	if (argc != 7)
	{
		print_usage();
		throw std::runtime_error("Too few or too many arguments.");
	}

	std::string service_name;
	int service_port;
	int testbed_port;

	bool name_found = false;
	bool service_port_found = false;
	bool testbed_port_found = false;

	for (size_t i = 1; i < argc; i += 2)
	{
		std::string arg = argv[i];
		std::string param = argv[i + 1];

		if (arg == "--name" || arg == "-n")
		{
			service_name = param;
			name_found = true;
		}
		else if (arg == "--port" || arg == "-p")
		{
			service_port = std::stoi(param);
			service_port_found = true;
		}
		else if (arg == "--testbed" || arg == "-t")
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

	if (!(name_found && service_port_found && testbed_port_found))
	{
		print_usage();
		throw std::runtime_error("Did not supply all arguments.");
	}

	return std::make_tuple(service_name, service_port, testbed_port);
}
