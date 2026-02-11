#include "RemoteBrokerServer.h"

#include <cstring>
#include <sstream>
#include <stdexcept>
#include <optional>
#include <iostream>

RemoteBrokerServer::RemoteBrokerServer(std::shared_ptr<MessageBroker> broker, uint16_t port, int num_workers)
	: m_Broker(broker), m_Server(port, num_workers)
{
	std::cerr << "[DEBUG] RemoteBrokerServer::ctor - broker ptr: " << m_Broker.get() << std::endl;
	std::cerr << "[DEBUG] RemoteBrokerServer::ctor - port: " << port << ", workers: " << num_workers << std::endl;

	// Register request handlers
	m_Server.RegisterRequestHandler("PUBLISH",
		[this](const std::string& req) { return HandlePublish(req); });
	m_Server.RegisterRequestHandler("GET_NEXT",
		[this](const std::string& req) { return HandleGetNext(req); });
	m_Server.RegisterRequestHandler("GET_CURRENT",
		[this](const std::string& req) { return HandleGetCurrent(req); });
	m_Server.RegisterRequestHandler("GET_RATE",
		[this](const std::string& req) { return HandleGetRate(req); });
	m_Server.RegisterRequestHandler("LIST_TOPICS",
		[this](const std::string& req) { return HandleListTopics(req); });
}

RemoteBrokerServer::~RemoteBrokerServer()
{
	Stop();
}

void RemoteBrokerServer::Start()
{
	m_Server.Start();
}

void RemoteBrokerServer::Stop()
{
	m_Server.Stop();
}

bool RemoteBrokerServer::IsRunning() const
{
	return m_Server.IsRunning();
}

std::string RemoteBrokerServer::HandlePublish(const std::string& request_data)
{
	std::cerr << "[DEBUG] HandlePublish called - request_size: " << request_data.size() << std::endl;

	try
	{
		// Deserialize the message
		auto msg_opt = DeserializeMessage(request_data);
		std::cerr << "[DEBUG] DeserializeMessage returned has_value: " << msg_opt.has_value() << std::endl;

		if (!msg_opt.has_value())
		{
			std::cerr << "[DEBUG] DeserializeMessage failed" << std::endl;
			return "ERROR: Failed to deserialize message";
		}

		Message& msg = msg_opt.value();
		std::cerr << "[DEBUG] Message topic: " << (msg.m_Header ? msg.m_Header->topic : "NULL") << std::endl;
		std::cerr << "[DEBUG] Message payload_size: " << msg.GetPayloadSize() << std::endl;
		std::cerr << "[DEBUG] m_Broker ptr: " << m_Broker.get() << std::endl;
		std::cerr << "[DEBUG] About to call PublishMessage..." << std::endl;

		// Publish to local broker
		m_Broker->PublishMessage(msg, true);

		std::cerr << "[DEBUG] PublishMessage completed successfully" << std::endl;
		return "OK";
	}
	catch (const std::exception& e)
	{
		std::cerr << "[ERROR] Exception in HandlePublish: " << e.what() << std::endl;
		return std::string("ERROR: ") + e.what();
	}
}

RemoteBrokerServer::GetNextParams RemoteBrokerServer::ParseGetNextRequest(const std::string& data)
{
	GetNextParams params;

	// Parse binary format: [topic_len (4 bytes)][topic][frame_id (8 bytes)][mode (4 bytes)][timeout (8 bytes)]
	if (data.length() < sizeof(uint32_t))
	{
		throw std::runtime_error("Invalid request data: too short");
	}

	size_t offset = 0;

	// Read topic length
	uint32_t topic_len;
	std::memcpy(&topic_len, &data[offset], sizeof(uint32_t));
	offset += sizeof(uint32_t);

	if (data.length() < offset + topic_len + sizeof(uint64_t) + sizeof(int) + sizeof(double))
	{
		throw std::runtime_error("Invalid request data: incomplete");
	}

	// Read topic
	params.topic = std::string(&data[offset], topic_len);
	offset += topic_len;

	// Read frame_id
	std::memcpy(&params.preferred_frame_id, &data[offset], sizeof(uint64_t));
	offset += sizeof(uint64_t);

	// Read mode
	int mode_int;
	std::memcpy(&mode_int, &data[offset], sizeof(int));
	params.mode = (mode_int == 0) ? MessageSubscriptionMode::NewestOnly : MessageSubscriptionMode::Sequential;
	offset += sizeof(int);

	// Read timeout
	std::memcpy(&params.timeout_seconds, &data[offset], sizeof(double));

	return params;
}

std::string RemoteBrokerServer::HandleGetNext(const std::string& request_data)
{
	try
	{
		// Parse request parameters
		GetNextParams params = ParseGetNextRequest(request_data);

		// Call GetNextMessage with timeout
		auto msg_opt = m_Broker->GetNextMessage(params.topic, params.preferred_frame_id,
		                                         params.mode, params.timeout_seconds);

		if (!msg_opt.has_value())
		{
			// Timeout - return empty response
			return "";
		}

		// Serialize and return the message
		return SerializeMessage(msg_opt.value());
	}
	catch (const std::exception& e)
	{
		return std::string("ERROR: ") + e.what();
	}
}

std::string RemoteBrokerServer::HandleGetCurrent(const std::string& request_data)
{
	try
	{
		// request_data is just the topic string
		auto msg_opt = m_Broker->GetCurrentMessage(request_data);

		if (!msg_opt.has_value())
		{
			// No message available - return empty response
			return "";
		}

		// Serialize and return the message
		return SerializeMessage(msg_opt.value());
	}
	catch (const std::exception& e)
	{
		return std::string("ERROR: ") + e.what();
	}
}

std::string RemoteBrokerServer::HandleGetRate(const std::string& request_data)
{
	try
	{
		// request_data is just the topic string
		double rate = m_Broker->GetMessageRate(request_data);

		// Convert to string
		return std::to_string(rate);
	}
	catch (const std::exception& e)
	{
		return std::string("ERROR: ") + e.what();
	}
}

std::string RemoteBrokerServer::HandleListTopics(const std::string& request_data)
{
	(void)request_data;  // Unused

	try
	{
		std::vector<std::string> topics = m_Broker->GetAllMessageTopics();

		// Format as comma-separated list
		std::string result;
		for (size_t i = 0; i < topics.size(); ++i)
		{
			if (i > 0) result += ",";
			result += topics[i];
		}

		return result;
	}
	catch (const std::exception& e)
	{
		return std::string("ERROR: ") + e.what();
	}
}

std::string RemoteBrokerServer::SerializeMessage(const Message& msg)
{
	// Serialize MessageHeader and payload into a string
	// Format: [header_size (4 bytes)][MessageHeader][payload]

	const MessageHeader* header = msg.m_Header;
	size_t payload_size = msg.GetPayloadSize();

	std::string result;
	result.resize(sizeof(uint32_t) + sizeof(MessageHeader) + payload_size);

	uint32_t header_size = sizeof(MessageHeader);
	std::memcpy(&result[0], &header_size, sizeof(uint32_t));
	std::memcpy(&result[sizeof(uint32_t)], header, sizeof(MessageHeader));

	if (payload_size > 0 && msg.m_Payload)
	{
		std::memcpy(&result[sizeof(uint32_t) + sizeof(MessageHeader)],
		            msg.m_Payload, payload_size);
	}

	return result;
}

std::optional<Message> RemoteBrokerServer::DeserializeMessage(const std::string& data)
{
	if (data.empty())
	{
		return std::nullopt;
	}

	// Deserialize from format: [header_size (4 bytes)][MessageHeader][payload]
	if (data.length() < sizeof(uint32_t))
	{
		return std::nullopt;
	}

	uint32_t header_size;
	std::memcpy(&header_size, data.data(), sizeof(uint32_t));

	if (data.length() < sizeof(uint32_t) + header_size)
	{
		return std::nullopt;
	}

	// Allocate header on heap
	MessageHeader* header = new MessageHeader();
	std::memcpy(header, data.data() + sizeof(uint32_t), header_size);

	// Calculate payload size and position
	size_t payload_size = data.length() - sizeof(uint32_t) - header_size;

	// Allocate payload buffer and copy data
	void* payload = nullptr;
	if (payload_size > 0)
	{
		payload = std::malloc(payload_size);
		if (!payload)
		{
			delete header;
			return std::nullopt;
		}
		std::memcpy(payload, data.data() + sizeof(uint32_t) + header_size, payload_size);
	}

	// Create message
	// Note: The caller takes ownership of the header and payload memory
	return std::optional<Message>(Message(header, payload, 0));
}
