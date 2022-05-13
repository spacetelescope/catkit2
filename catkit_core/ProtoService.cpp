#include "Service.h"

#include "TimeStamp.h"
#include "service.pb.h"

#include <chrono>
#include <csignal>
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <zmq_addon.hpp>

using namespace zmq;
using json = nlohmann::json;
using namespace std::string_literals;

const int HEARTBEAT_LIVENESS = 5;
const float HEARTBEAT_INTERVAL = 1; // sec

static sig_atomic_t interrupt_signal = 0;
static void SignalHandler(int signal_value)
{
	interrupt_signal = 1;
}

ProtoService::ProtoService(std::string service_name, std::string service_type, int server_port)
	: m_ShellSocket(nullptr),
	m_ServiceName(service_name), m_ServiceType(service_type),
	m_Port(testbed_port), m_IsRunning(false),
	m_HasGottenConfiguration(false), m_IsOpened(false),
	m_LoggerConsole(), m_LoggerPublish(service_name, "tcp://localhost:"s + std::to_string(server_port + 1))
{
	LOG_INFO("Initializing service '"s + service_name + "'.");

	// Catching Ctrl+C and similar process killers and shut down gracefully.
	signal(SIGINT, SignalHandler);
	signal(SIGTERM, SignalHandler);

	// Set up request handlers.
	m_RequestHandlers["get_property"] = [this](const string &data){return this->OnGetPropertyRequest(data);};
	m_RequestHandlers["set_property"] = [this](const string &data){return this->OnSetPropertyRequest(data);};

	m_RequestHandlers["execute_command"] = [this](const string &data){return this->OnExecuteCommandRequest(data);};

	m_RequestHandlers["info"] = [this](const string &data){return this->OnGetInfoRequest(data);};

	MakeProperty("config", [this](){return this->GetConfiguration();});
	m_ServiceHeartbeat = MakeDataStream("heartbeat", DataType::DT_UINT64, {1}, 10);

	uint64_t start_time = GetTimeStamp();
	m_ServiceHeartbeat->SubmitData(&start_time);

	LOG_INFO("Service '"s + service_name + "' has been initialized.");

	m_InterfaceThread = std::thread(&ProtoService::MonitorInterface, this);
}

ProtoService::~ProtoService()
{
	LOG_INFO("Service '"s + m_ServiceName + "' is being destroyed.");

	m_IsRunning = false;

	if (m_InterfaceThread.joinable())
		m_InterfaceThread.join();

	LOG_INFO("Service '"s + m_ServiceName + "' has been destroyed.");
}

void ProtoService::MonitorInterface()
{
	LOG_INFO("Connecting to testbed server on port "s + std::to_string(m_Port) + ".");

	m_ShellSocket = new socket_t(m_Context, ZMQ_ROUTER);
	m_ServerSocket = new socket_t(m_Context, ZMQ_DEALER);

	m_ShellSocket->set(zmq::sockopt::rcvtimeo, 100);
	m_ShellSocket->set(zmq::sockopt::linger, 0);

	m_ServerSocket->set(zmq::sockopt::rcvtimeo, 500);
	m_ServerSocket->set(zmq::sockopt::linger, 0);

	m_ShellSocket->bind("tcp://127.0.0.1:*");
	m_ServerSocket->connect("tcp://127.0.0.1:"s + to_string(m_ServerPort));

	const string endpoint = m_ShellSocket->get(zmq::sockopt::last_endpoint);
	const string port_string = endpoint.substr(endpoint.rfind(":") + 1);
	m_ServicePort = stoi(port_string);

	m_IsRunning = true;
	m_LastReceivedHeartbeatTime = GetTimeStamp();
	m_LastSentHeartbeatTime = GetTimeStamp();

	SendRegisterMessage();

	bool sent_opened_message = false;

	while (m_IsRunning && !interrupt_signal)
	{
		// Send message that we are open for business, but only once.
		if (m_IsOpened && !sent_opened_message)
		{
			SendOpenedMessage();
			sent_opened_message = true;
		}

		// Send heartbeat if enough time has passed.
		if ((m_LastSentHeartbeatTime + HEARTBEAT_INTERVAL * 1e9) < GetTimeStamp())
			SendHeartbeatMessage();

		// Check received heartbeats to see if the server crashed.
		if ((m_LastReceivedHeartbeatTime + HEARTBEAT_INTERVAL * HEARTBEAT_LIVENESS * 1e9) < GetTimeStamp())
		{
			LOG_CRITICAL("No heartbeats received from the server in a while. Quiting for safety reasons.");

			m_IsRunning = false;
			break;
		}

		message_t frame0, frame1, frame2, frame3;

		try
		{
			multipart_t parts;
			auto res = recv_multipart(*m_ShellSocket, std::back_inserter(parts));

			if (!res.has_value())
			{
				// Socket timed out, so continue and try again.
				// This is done to facilitate periodic error/shutdown/interrupt checking.
				continue;
			}

			if (parts.size() < 2)
			{
				LOG_ERROR("Incoming message had only "s + std::to_string(parts.size()) + "< 2 parts.");

				// Ignore message.
				continue;
			}

			// Extract the first two parts (first is empty, second is message type).
			parts.pop();
			std::string message_type = parts.popstr();

			if (message_type == HEARTBEAT_ID)
			{
				m_LastReceivedHeartbeatTime = GetTimeStamp();
			}
			else if (message_type == CONFIGURATION_ID)
			{
				LOG_DEBUG("Received configuration.");

				if (parts.size() < 1)
				{
					LOG_ERROR("Message had too little parts.");

					// Ignore message.
					continue;
				}

				std::string json_string = parts.popstr();

				json body;
				try
				{
					body = json::parse(json_string);
				}
				catch (...)
				{
					LOG_ERROR("Received malformed JSON body from server.");

					// Ignore message.
					continue;
				}

				m_Configuration = body;
				m_HasGottenConfiguration = true;
			}
			else if (message_type == REQUEST_ID)
			{
				LOG_DEBUG("Received request.");

				if (parts.size() < 2)
				{
					LOG_ERROR("Message had too little parts.");

					// Ignore message.
					continue;
				}

				std::string client_identity = parts.popstr();
				std::string json_string = parts.popstr();

				json request;
				try
				{
					request = json::parse(json_string);
				}
				catch (...)
				{
					LOG_ERROR("Received malformed JSON from the server.");

					// Ignore message.
					continue;
				}

				// Check if request contains a type and data.
				if (!request.count("request_type") || !request.count("data"))
				{
					LOG_ERROR("Requests are required to contain a request_type and data. Discarding message.");

					// Ignore message.
					continue;
				}

				std::string request_type = request["request_type"].get<std::string>();
				json data = request["data"];

				// Handle message according to request_type.
				if (m_RequestHandlers.find(request_type) != m_RequestHandlers.end())
				{
					json reply_data;

					try
					{
						reply_data = m_RequestHandlers[request_type](data);

						SendReplyOk(client_identity, request_type, reply_data);
					}
					catch (std::exception &e)
					{
						LOG_ERROR("Encountered error during handling of request: "s + e.what());
						SendReplyError(client_identity, request_type, e.what());
					}
				}
				else
				{
					std::string error = "Type of message \""s + request_type + "\" not recognized. Discarding message.";
					LOG_ERROR(error);

					SendReplyError(client_identity, request_type, error);
					continue;
				}
			}
		}
		catch (zmq::error_t)
		{
			if (!interrupt_signal)
				LOG_ERROR("Error while receiving message.");
		}
	}

	m_IsRunning = false;
	try
	{
		this->ShutDown();
	}
	catch (...)
	{
		LOG_ERROR("Caught error during call to shut down. Ignoring...");
	}

	m_ShellSocket->close();
	delete m_ShellSocket;
	m_ShellSocket = nullptr;

	if (interrupt_signal)
		LOG_INFO("Service '" + m_ServiceName + "' interrupted by terminate signal. Shutting down.");
	else
		LOG_INFO("Service '" + m_ServiceName + "' shut down with keyboard interrupt.");
}

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

void ProtoService::Run()
{
	m_ShouldShutDown = false;

	std::jthread service_thread = std::jthread(&ProtoService::RunService);

	MonitorInterface();
}

void ProtoService::Sleep(double sleep_time_in_ms, void (*error_check)()=nullptr)
{
	Timer timer;

	while (true)
	{
		double sleep_remaining = sleep_time_in_ms - timer.GetTime() * 1000;

		if (sleep_remaining > 0)
			break;

		if (m_ShouldShutDown)
			break;

		if (error_check)
			error_check();

		std::this_thread::sleep_for(chrono::milliseconds(min(20, sleep_remaining)));
	}
}

void ProtoService::ShutDown()
{
	m_ShouldShutDown = true;
}

void ProtoService::RunService()
{
	m_IsRunning = true;

	Finally end_service([this]()
	{
		m_IsRunning = false;
	});

	LOG_INFO("Opening service...");

	try
	{
		this->Open();
		m_IsOpened = true;
	}
	catch (...)
	{
		LOG_ERROR("Caught exception during opening of Service. Exiting...");
		throw;
	}

	LOG_INFO("Service succesfully opened. Starting main loop.");

	try
	{
		this->Main();
	}
	catch (...)
	{
		LOG_ERROR("Caught exception in main function of Service. Closing Service and exiting...");

		this->Close();
		m_IsOpened = false;
		throw;
	}

	LOG_INFO("Main loop has ended. Closing service...");

	try
	{
		this->Close();
		m_IsOpened = false;
	}
	catch (...)
	{
		LOG_ERROR("Caught exception during closing of Service. Exiting...");
		throw;
	}

	LOG_INFO("Service has successfully been closed.");
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
	LOG_CRITICAL("You MUST override the shut_down() function for correct shutdown behaviour.");
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
	// Wait for configuration to arrive.
	while (!m_HasGottenConfiguration)
	{
		std::this_thread::sleep_for(std::chrono::milliseconds(10));
	}

	return m_Configuration;
}

const std::string &Service::GetServiceName() const
{
	return m_ServiceName;
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
	auto stream = DataStream::Create(stream_name, GetServiceName(), type, dimensions, num_frames_in_buffer);
	m_DataStreams[stream_name] = stream;

	return stream;
}

std::shared_ptr<DataStream> Service::ReuseDataStream(std::string stream_name, std::string stream_id)
{
	auto stream = DataStream::Open(stream_id);
	m_DataStreams[stream_name] = stream;

	return stream;
}

json Service::OnGetPropertyRequest(const nlohmann::json &data)
{
	if (!data.count("property_name"))
		throw std::runtime_error("Request must contain a property name.");

	std::string property_name = data["property_name"];
	auto property = GetProperty(property_name);

	if (!property)
		throw std::runtime_error("Property \""s + property_name + "\" does not exist.");

	return property->Get();
}

json Service::OnSetPropertyRequest(const nlohmann::json &data)
{
	if (!data.count("property_name"))
		throw std::runtime_error("Request must contain a property name.");

	std::string property_name = data["property_name"];
	auto property = GetProperty(property_name);

	if (!property)
		throw std::runtime_error("Property \""s + property_name + "\" does not exist.");

	if (!data.count("value"))
		throw std::runtime_error("Request must contain a value.");

	property->Set(data["value"]);

	return json();
}

json Service::OnExecuteCommandRequest(const nlohmann::json &data)
{
	if (!data.count("command_name"))
		throw std::runtime_error("Request must contain a command name.");

	std::string command_name = data["command_name"];
	auto command = GetCommand(command_name);

	if (!command)
		throw std::runtime_error("Command \""s + command_name + "\" does not exist.");

	if (!data.count("arguments"))
		throw std::runtime_error("Request must contain arguments.");

	return command->Execute(data["arguments"]);
}

json Service::OnGetDataStreamInfoRequest(const nlohmann::json &data)
{
	if (!data.count("stream_name"))
		throw std::runtime_error("Request must contain a stream name.");

	std::string stream_name = data["stream_name"];
	auto stream = GetDataStream(stream_name);

	if (!stream)
		throw std::runtime_error("DataStream \""s + stream_name + "\" does not exist.");

	json info = {
		{"stream_id", stream->GetStreamId()}
	};

	return info;
}

json Service::OnAllPropertiesRequest(const nlohmann::json &data)
{
	std::vector<std::string> properties;
	for (auto const &i : m_Properties)
		properties.push_back(i.first);

	return json(properties);
}

json Service::OnAllCommandsRequest(const nlohmann::json &data)
{
	std::vector<std::string> commands;
	for (auto const &i : m_Commands)
		commands.push_back(i.first);

	return json(commands);
}

json Service::OnAllDataStreamsRequest(const nlohmann::json &data)
{
	std::map<std::string, std::string> streams;
	for (auto const &i : m_DataStreams)
		streams[i.first] = i.second->GetStreamId();

	return json(streams);
}

json Service::OnShutdownRequest(const nlohmann::json &data)
{
	m_IsRunning = false;

	return json();
}

void Service::SendReplyMessage(const std::string &client_identity, const nlohmann::json &reply)
{
	LOG_DEBUG("Sending reply message.");

	multipart_t msg;

	msg.addstr("");
	msg.addstr(SERVICE_ID);
	msg.addstr(m_ServiceName);
	msg.addstr(REPLY_ID);
	msg.addstr(client_identity);
	msg.addstr(reply.dump());

	msg.send(*m_ShellSocket);
}

void Service::SendReplyOk(const std::string &client_identity, const std::string &reply_type, const nlohmann::json &data)
{
	json reply = {
		{"status", "ok"},
		{"description", "success"},
		{"reply_type", reply_type},
		{"data", data}
	};

	SendReplyMessage(client_identity, reply);
}

void Service::SendReplyError(const std::string &client_identity, const std::string &reply_type, const std::string &error_description)
{
	json reply = {
		{"status", "error"},
		{"description", error_description},
		{"reply_type", reply_type},
		{"data", json()}
	};

	SendReplyMessage(client_identity, reply);
}

void Service::SendOpenedMessage()
{
	LOG_DEBUG("Sending opened message.");

	multipart_t msg;

	msg.addstr("");
	msg.addstr(SERVICE_ID);
	msg.addstr(m_ServiceName);
	msg.addstr(OPENED_ID);

	msg.send(*m_ShellSocket);
}

void Service::SendRegisterMessage()
{
	LOG_DEBUG("Sending register message.");

	json data = {
		{"pid", GetCurrentProcessId()},
		{"service_type", m_ServiceType}
	};

	multipart_t msg;

	msg.addstr("");
	msg.addstr(SERVICE_ID);
	msg.addstr(m_ServiceName);
	msg.addstr(REGISTER_ID);
	msg.addstr(data.dump());

	msg.send(*m_ShellSocket);
}

void Service::SendHeartbeatMessage()
{
	multipart_t msg;

	msg.addstr("");
	msg.addstr(SERVICE_ID);
	msg.addstr(m_ServiceName);
	msg.addstr(HEARTBEAT_ID);

	msg.send(*m_ShellSocket);

	m_LastSentHeartbeatTime = GetTimeStamp();

	m_HeartbeatStream->SubmitData(&m_LastSentHeartbeatTime);
}

void print_usage()
{
	std::cout << "Usage:\n  service --name NAME --port PORT";
}

std::tuple<std::string, int> ParseServiceArgs(int argc, char *argv[])
{
	if (argc != 5)
	{
		print_usage();
		throw std::runtime_error("Too few or too many arguments.");
	}

	std::string service_name;
	int testbed_port;

	bool name_found = false;
	bool port_found = false;

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
			testbed_port = std::stoi(param);
			port_found = true;
		}
		else
		{
			print_usage();
			throw std::runtime_error(std::string("Invalid argument '") + arg);
		}
	}

	if (!(name_found && port_found))
	{
		print_usage();
		throw std::runtime_error("Did not supply all arguments.");
	}

	return std::make_tuple(service_name, testbed_port);
}