#include "Module.h"

#include "Log.h"

#include <csignal>
#include <algorithm>
#include <string>
#include <locale>
#include <stdexcept>
#include <cstring>
#include <utility>
#include <memory>
#include <map>
#include <array>
#include <iostream>
#include <functional>

using namespace zmq;
using json = nlohmann::json;
using namespace std::literals::string_literals;

static sig_atomic_t interrupt_signal = 0;
static void SignalHandler(int signal_value)
{
	interrupt_signal = 1;
}

Module::Module(std::string name, int port)
	: m_Name(name), m_Port(port), m_IsRunning(false),
	m_Context(nullptr), m_Shell(nullptr), m_Broadcast(nullptr)
{
	m_Logger = std::make_shared<LogConsole>(true, true);
	SubscribeToLog(m_Logger);

	LOG_INFO("Starting module '"s + name + "' on port "s  + std::to_string(port) + ".");

	// Catching Ctrl+C and similar process killers and shut down gracefully.
	signal(SIGINT, SignalHandler);
	signal(SIGTERM, SignalHandler);

	// Set up SerializedMessage handlers.
	m_MessageHandlers["execute_command_request"] = [this](const SerializedMessage &request, SerializedMessage &reply){this->HandleExecuteCommandRequest(request, reply);};

	m_MessageHandlers["get_property_request"] = [this](const SerializedMessage &request, SerializedMessage &reply){this->HandleGetPropertyRequest(request, reply);};
	m_MessageHandlers["set_property_request"] = [this](const SerializedMessage &request, SerializedMessage &reply){this->HandleSetPropertyRequest(request, reply);};

	m_MessageHandlers["list_all_properties_request"] = [this](const SerializedMessage &request, SerializedMessage &reply){this->HandleListAllPropertiesRequest(request, reply);};
	m_MessageHandlers["list_all_commands_request"] = [this](const SerializedMessage &request, SerializedMessage &reply){this->HandleListAllCommandsRequest(request, reply);};
	m_MessageHandlers["list_all_data_streams_request"] = [this](const SerializedMessage &request, SerializedMessage &reply){this->HandleListAllDataStreamsRequest(request, reply);};

	m_MessageHandlers["get_name_request"] = [this](const SerializedMessage &request, SerializedMessage &reply){this->HandleGetNameRequest(request, reply);};

	m_MessageHandlers["shut_down_request"] = [this](const SerializedMessage &request, SerializedMessage &reply){this->HandleShutdownRequest(request, reply);};

	LOG_INFO("Module '"s + name + "' has started.");
}

Module::~Module()
{
	LOG_INFO("Module '"s + m_Name + "' is being destroyed.");

	if (m_IsRunning)
	{
		m_IsRunning = false;

		if (m_InterfaceThread.joinable())
			m_InterfaceThread.join();
	}

	LOG_INFO("Module '"s + m_Name + "' has been destroyed.");
	UnsubscribeToLog(m_Logger);
}

void Module::MonitorInterface()
{
	m_Context = new context_t(1);
	m_Shell = new socket_t(*m_Context, ZMQ_REP);
	m_Broadcast = new socket_t(*m_Context, ZMQ_PUB);

	m_Shell->set(zmq::sockopt::rcvtimeo, 20);
	m_Shell->set(zmq::sockopt::linger, 0);
	m_Broadcast->set(zmq::sockopt::linger, 0);

	m_Shell->bind("tcp://*:"s + std::to_string(m_Port));
	m_Broadcast->bind("tcp://*:"s + std::to_string(m_Port + 1));

	m_IsRunning = true;

	while (m_IsRunning && !interrupt_signal)
	{
		message_t request;
		message_t request_binary;
		SerializedMessage module_message;

		try
		{
			// TODO: check return value.
			auto res = m_Shell->recv(request);

			if (!res.has_value())
			{
				// Socket timed out, so continue and try again.
				// This is done to facilitate periodic error/shutdown/interrupt checking.
				continue;
			}

			std::string json_string((const char *) request.data(), request.size());

			// Check if binary data was included.
			if (request.more())
			{
				// Receive binary data blob.
				// TODO: check return value.
				res = m_Shell->recv(request_binary);
			}
			else
			{
				// Message did not include binary data.
				module_message.binary_data.clear();
			}

			// Discard further message parts.
			while (request.more())
			{
				// TODO: check return value.
				res = m_Shell->recv(request_binary);
			}

			LOG_DEBUG("Request received: " + json_string);

			json message;
			try
			{
				message = json::parse(json_string);
			}
			catch (...)
			{
				LOG_ERROR("Malformed JSON. Discarding.");

				SerializedMessage reply;
				reply.data["status"] = "error";
				reply.data["status_description"] = "Malformed JSON.";

				SendReplyMessage("module_error", reply);
				continue;
			}

			// Parse message type
			if (!message.count("message_type"))
			{
				LOG_ERROR("Module messages are required to contain a type. Discarding message.");

				SerializedMessage reply;
				reply.data["status"] = "error";
				reply.data["status_description"] = "Message doesn't contain a message_type.";

				SendReplyMessage("module_error", reply);
				continue;
			}

			std::string message_type = message["message_type"].get<std::string>();

			if (!message.count("message_data"))
			{
				module_message.data = json::object();
			}
			else
			{
				module_message.data = message["message_data"];
			}

			// Handle message according to message_type.
			if (m_MessageHandlers.find(message_type) != m_MessageHandlers.end())
			{
				SerializedMessage reply;
				try
				{
					m_MessageHandlers[message_type](module_message, reply);

					reply.data["status"] = "ok";
					SendReplyMessage(message_type.substr(0,message_type.size() - 7) + "reply", reply);
				}
				catch (std::exception &e)
				{
					reply.data["status"] = "error";
					reply.data["status_description"] = e.what();
					SendReplyMessage(message_type.substr(0,message_type.size() - 7) + "reply", reply);
				}
			}
			else
			{
				LOG_ERROR("Type of message (\""s + message_type + "\" not recognized. Discarding message.");

				SerializedMessage reply;
				reply.data["status"] = "error";
				reply.data["status_description"] = "Type of message (\""s + message_type + "\" not recognized.";

				SendReplyMessage("module_error", reply);
				continue;
			}
		}
		catch (zmq::error_t)
		{
			if (!interrupt_signal)
				LOG_ERROR("Error while receiving message.");
		}
	}

	m_IsRunning = false;
	this->ShutDown();

	delete m_Broadcast;
	m_Broadcast = nullptr;

	delete m_Shell;
	m_Shell = nullptr;

	delete m_Context;
	m_Context = nullptr;

	if (interrupt_signal)
		LOG_INFO("Module '" + m_Name + "' interrupted by user. Shutting down.");
	else
		LOG_INFO("Module '" + m_Name + "' shut down by user.");
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

void Module::Run()
{
	try
	{
		this->Open();
	}
	catch (...)
	{
		LOG_ERROR("Caught exception during opening of Module. Exiting...");
		throw;
	}

	m_InterfaceThread = std::thread(&Module::MonitorInterface, this);

	// Shut down monitoring thread at the end of this function no matter what.
	Finally cleanup_interface_thread([this]()
	{
		m_IsRunning = false;

		try
		{
			m_InterfaceThread.join();
		}
		catch (...)
		{
			// Thread was already stopped. Ignore errors.
		}
	});

	try
	{
		this->Main();
	}
	catch (...)
	{
		LOG_ERROR("Caught exception in main function of Module. Closing module and exiting...");

		this->Close();
		throw;
	}

	try
	{
		this->Close();
	}
	catch (...)
	{
		LOG_ERROR("Caught exception during closing of Module. Exiting...");
		throw;
	}
}

std::string Module::GetName()
{
	return m_Name;
}

void Module::Open()
{
}

void Module::Main()
{
}

void Module::Close()
{
}

void Module::ShutDown()
{
}

std::shared_ptr<Property> Module::GetProperty(const std::string &property_name)
{
	auto i = m_Properties.find(property_name);

	if (i != m_Properties.end())
		return i->second;
	else
		return nullptr;
}

std::shared_ptr<Command> Module::GetCommand(const std::string &command_name)
{
	auto i = m_Commands.find(command_name);

	if (i != m_Commands.end())
		return i->second;
	else
		return nullptr;
}

std::shared_ptr<DataStream> Module::GetDataStream(const std::string &stream_name)
{
	auto i = m_DataStreams.find(stream_name);

	if (i != m_DataStreams.end())
		return i->second;
	else
		return nullptr;
}

void Module::HandleExecuteCommandRequest(const SerializedMessage &request, SerializedMessage &reply)
{
	if (!request.data.count("command_name"))
		throw SerializationError("Request must contain a command_name.");

	std::string command_name = request.data["command_name"];
	auto command = GetCommand(command_name);

	if (!command)
		throw SerializationError("Command \'"s + command_name + "\' does not exist.");

	reply.data["result"] = command->Execute(request.data["arguments"]);

	// Broadcast executed command
	SerializedMessage broadcast;
	broadcast.data["command_name"] = command_name;

	SendBroadcastMessage("execute_command_broadcast", broadcast);
}

void Module::HandleGetPropertyRequest(const SerializedMessage &request, SerializedMessage &reply)
{
	if (!request.data.count("property_name"))
		throw SerializationError("Request must contain a property_name.");

	std::string property_name = request.data["property_name"];
	auto property = GetProperty(property_name);

	if (!property)
		throw SerializationError("Property \'"s + property_name + "\' does not exist.");

	reply.data["value"] = property->Get();
}

void Module::HandleSetPropertyRequest(const SerializedMessage &request, SerializedMessage &reply)
{
	if (!request.data.count("property_name"))
		throw SerializationError("Request must contain a property_name.");

	std::string property_name = request.data["property_name"];
	auto property = GetProperty(property_name);

	if (!property)
		throw SerializationError("Property \'"s + property_name + "\' does not exist.");

	if (!request.data.count("value"))
		throw SerializationError("Tried to set property \'"s + property_name + "\' without a value.");

	property->Set(request.data["value"]);

	// Broadcast changed property
	SerializedMessage broadcast;
	broadcast.data["property_name"] = property_name;

	SendBroadcastMessage("set_property_broadcast", broadcast);
}

void Module::HandleListAllPropertiesRequest(const SerializedMessage &request, SerializedMessage &reply)
{
	std::vector<std::string> properties;
	for (auto const &i : m_Properties)
		properties.push_back(i.first);

	reply.data["value"] = properties;
}

void Module::HandleListAllCommandsRequest(const SerializedMessage &request, SerializedMessage &reply)
{
	std::vector<std::string> commands;
	for (auto const &i : m_Commands)
		commands.push_back(i.first);

	reply.data["value"] = commands;
}

void Module::HandleListAllDataStreamsRequest(const SerializedMessage &request, SerializedMessage &reply)
{
	std::vector<std::string> data_streams;
	for (auto const &i : m_DataStreams)
		data_streams.push_back(i.first);

	reply.data["value"] = data_streams;
}

void Module::HandleGetNameRequest(const SerializedMessage &request, SerializedMessage &reply)
{
	reply.data["value"] = m_Name;
}

void Module::HandleShutdownRequest(const SerializedMessage &request, SerializedMessage &reply)
{
	m_IsRunning = false;
}

void Module::SendReplyMessage(const std::string &type, const SerializedMessage &message)
{
	// Serialize reply message.
	json reply_message;

	reply_message["message_type"] = type;
	reply_message["message_data"] = message.data;

	std::string json_message = reply_message.dump();

	// Construct and send message
	message_t message_zmq(json_message.size());
	char *message_zmq_data = (char *) message_zmq.data();
	memcpy((char *) message_zmq.data(), json_message.data(), json_message.size());

	if (message.binary_data.empty())
	{
		if (m_Shell)
			m_Shell->send(message_zmq, send_flags::none);
	}
	else
	{
		if (m_Shell)
			m_Shell->send(message_zmq, send_flags::sndmore);

		message_t binary_zmq(message.binary_data.size());
		memcpy((char *) binary_zmq.data(), message.binary_data.data(), message.binary_data.size());

		if (m_Shell)
			m_Shell->send(binary_zmq, send_flags::none);
	}

	LOG_DEBUG("Reply sent: " + json_message);
}

void Module::SendBroadcastMessage(const std::string &type, const SerializedMessage &message)
{
	// Serialize broadcast message
	json broadcast_message;

	broadcast_message["message_type"] = type;
	broadcast_message["message_data"] = message.data;

	std::string json_message = broadcast_message.dump();

	// Construct and send message
	message_t message_zmq(json_message.size());
	memcpy(message_zmq.data(), json_message.c_str(), json_message.size());

	if (m_Broadcast)
		m_Broadcast->send(message_zmq, send_flags::none);
}

void Module::RegisterProperty(std::shared_ptr<Property> property)
{
	auto property_name = property->GetName();
	m_Properties[property_name] = property;

	LOG_DEBUG("Property \'"s + property_name + "\' registered.");
}

void Module::RegisterCommand(std::shared_ptr<Command> command)
{
	auto command_name = command->GetName();
	m_Commands[command_name] = command;

	LOG_DEBUG("Command \'"s + command_name + "\' registered.");
}

void Module::RegisterDataStream(std::shared_ptr<DataStream> stream)
{
	auto stream_name = stream->GetStreamName();
	m_DataStreams[stream_name] = stream;

	LOG_DEBUG("DataStream \'"s + stream_name + "\' registered.");
}
