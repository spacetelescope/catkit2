#include "RemoteMessageBroker.h"
#include "LocalMessageBroker.h"

#include <cstring>
#include <sstream>
#include <stdexcept>
#include <optional>
#include <iostream>

#define DEBUG_PRINT(msg) std::cerr << "[DEBUG] " << __func__ << ":" << __LINE__ << " - " << msg << std::endl
#define ERROR_PRINT(msg) std::cerr << "[ERROR] " << __func__ << ":" << __LINE__ << " - " << msg << std::endl

// =============================================================================
// RemoteMessageBroker Implementation
// =============================================================================

RemoteMessageBroker::RemoteMessageBroker(std::shared_ptr<LocalMessageBroker> local_broker,
                                          const std::string& local_machine_name,
                                          const std::vector<PeerConfig>& peers)
	: m_LocalBroker(local_broker), m_LocalMachineName(local_machine_name)
{
	DEBUG_PRINT("local_machine: " << local_machine_name << ", peer count: " << peers.size());
	// Create Client objects for each peer
	for (const auto& peer : peers)
	{
		DEBUG_PRINT("peer: " << peer.name << " @ " << peer.host << ":" << peer.port);
		m_PeerClients[peer.name] = std::make_unique<Client>(peer.host, peer.port);
	}
}

RemoteMessageBroker::~RemoteMessageBroker()
{
	DEBUG_PRINT("destructor called");
	// Temporary buffers are automatically cleaned up by unordered_map destructor
}

bool RemoteMessageBroker::IsLocalTopic(std::string_view topic)
{
	std::string prefix = m_LocalMachineName + "/";
	bool is_local = topic.substr(0, prefix.length()) == prefix;
	DEBUG_PRINT("topic: " << topic << ", prefix: " << prefix << ", is_local: " << is_local);
	return is_local;
}

std::string RemoteMessageBroker::GetMachineFromTopic(std::string_view topic)
{
	size_t slash_pos = topic.find('/');
	std::string machine = (slash_pos == std::string_view::npos) ? std::string(topic) : std::string(topic.substr(0, slash_pos));
	DEBUG_PRINT("topic: " << topic << ", slash_pos: " << slash_pos << ", machine: " << machine);
	return machine;
}

Client& RemoteMessageBroker::GetClientForMachine(const std::string& machine)
{
	auto it = m_PeerClients.find(machine);
	bool found = (it != m_PeerClients.end());
	DEBUG_PRINT("machine: " << machine << ", found: " << found << ", peer_count: " << m_PeerClients.size());
	if (!found)
	{
		throw std::runtime_error("Unknown peer: " + machine);
	}
	return *(it->second);
}

Message RemoteMessageBroker::PrepareMessageImpl(std::string_view topic, size_t payload_size,
                                                Uuid trace_id, uint8_t memory_block_id)
{
	DEBUG_PRINT("topic: " << topic << ", payload_size: " << payload_size << ", IsLocalTopic: " << IsLocalTopic(topic));

	if (IsLocalTopic(topic))
	{
		// Local topic: use LocalMessageBroker's shared memory
		return m_LocalBroker->PrepareMessageImpl(topic, payload_size, trace_id, memory_block_id);
	}
	else
	{
		// Remote topic: allocate heap memory for both header and payload
		std::string topic_str(topic);

		// Allocate header on heap
		MessageHeader* header = new MessageHeader();
		std::memset(header, 0, sizeof(MessageHeader));

		// Allocate payload on heap
		void* payload = new uint8_t[payload_size];
		DEBUG_PRINT("allocated header: " << header << ", payload: " << payload);

		// Copy topic
		std::strncpy(header->topic, topic_str.c_str(), TOPIC_MAX_KEY_SIZE - 1);
		header->topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';

		// Set trace_id
		header->trace_id = trace_id;

		// Set payload info
		header->payload_info.total_size = payload_size;
		header->payload_info.memory_block_id = memory_block_id;
		header->payload_info.offset_in_buffer = 0;

		// Set timestamp
		header->producer_timestamp = 0;  // Will be set on publish

		return Message(header, payload, 0);
	}
}

std::string RemoteMessageBroker::SerializeMessage(const Message& msg)
{
	// Serialize MessageHeader and payload into a string
	// Format: [topic][payload_size][memory_block_id][payload]
    const size_t TOPIC_OFFSET = 0;
    const size_t PAYLOAD_SIZE_OFFSET = TOPIC_MAX_KEY_SIZE;
    const size_t MEMORY_BLOCK_ID_OFFSET = TOPIC_MAX_KEY_SIZE + sizeof(std::uint64_t);
    const size_t PAYLOAD_OFFSET = TOPIC_MAX_KEY_SIZE + sizeof(std::uint64_t) + sizeof(std::uint8_t);

	// Safety check - header should never be null
	if (!msg.m_Header)
	{
		throw std::runtime_error("Cannot serialize message with null header");
	}

	const MessageHeader &header = *msg.m_Header;
	size_t payload_size = msg.GetPayloadSize();

	std::string result;
	result.resize(PAYLOAD_OFFSET + payload_size);

    std::memcpy(&result[TOPIC_OFFSET], msg.GetTopic().data(), TOPIC_MAX_KEY_SIZE);
    std::memcpy(&result[PAYLOAD_SIZE_OFFSET], &payload_size, sizeof(std::uint64_t));
    std::memcpy(&result[MEMORY_BLOCK_ID_OFFSET], &header.payload_info.memory_block_id, sizeof(std::uint8_t));
	std::memcpy(&result[PAYLOAD_OFFSET], msg.GetPayload().data, payload_size);

	return result;
}

Message RemoteMessageBroker::PublishMessage(Message message, bool is_final)
{
	std::string topic(message.GetTopic());
	DEBUG_PRINT("topic: " << topic << ", is_final: " << is_final << ", IsLocalTopic: " << IsLocalTopic(topic));

	if (IsLocalTopic(topic))
	{
		// Local topic: delegate to LocalMessageBroker
		DEBUG_PRINT("delegating to local broker");
		return m_LocalBroker->PublishMessage(message, is_final);
	}
	else
	{
        // Only actually request the server to publish when the message is complete.
        // TODO: make sure this is correct. Maybe some frame ids need to be updated.
        if (!is_final)
            return message;

		// Remote topic: serialize and send over network
		std::string machine = GetMachineFromTopic(topic);
		DEBUG_PRINT("remote machine: " << machine);
		Client& client = GetClientForMachine(machine);
		DEBUG_PRINT("got client");

		// Serialize the message
		std::string serialized = SerializeMessage(message);
		DEBUG_PRINT("serialized size: " << serialized.size());

		// Send to remote
		DEBUG_PRINT("calling client.MakeRequest...");
		std::string response = client.MakeRequest("PUBLISH", serialized);
		DEBUG_PRINT("response: " << response);

		if (response != "OK")
		{
			throw std::runtime_error("Remote publish failed: " + response);
		}

		// Clean up heap-allocated memory from the message
		delete message.m_Header;
		delete[] static_cast<uint8_t*>(message.m_Payload);

		// Return a consumed message with null pointers
		return Message(nullptr, nullptr, 0);
	}
}

std::string RemoteMessageBroker::SerializeGetNextRequest(const std::string& topic,
                                                         uint64_t frame_id,
                                                         int mode,
                                                         double timeout)
{
	DEBUG_PRINT("topic: " << topic << ", frame_id: " << frame_id << ", mode: " << mode << ", timeout: " << timeout);
	// Simple binary serialization
	// Format: [topic_len (4 bytes)][topic][frame_id (8 bytes)][mode (4 bytes)][timeout (8 bytes)]

	std::string result;
	uint32_t topic_len = topic.length();

	result.resize(sizeof(uint32_t) + topic_len + sizeof(uint64_t) + sizeof(int) + sizeof(double));

	size_t offset = 0;
	std::memcpy(&result[offset], &topic_len, sizeof(uint32_t));
	offset += sizeof(uint32_t);

	std::memcpy(&result[offset], topic.data(), topic_len);
	offset += topic_len;

	std::memcpy(&result[offset], &frame_id, sizeof(uint64_t));
	offset += sizeof(uint64_t);

	std::memcpy(&result[offset], &mode, sizeof(int));
	offset += sizeof(int);

	std::memcpy(&result[offset], &timeout, sizeof(double));

	DEBUG_PRINT("serialized size: " << result.size());
	return result;
}

std::optional<Message> RemoteMessageBroker::DeserializeMessage(const std::string& data,
                                                               std::vector<uint8_t>& buffer)
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

	// Copy payload to provided buffer
	size_t payload_size = data.length() - sizeof(uint32_t) - header_size;
	buffer.resize(payload_size);
	if (payload_size > 0)
	{
		std::memcpy(buffer.data(), data.data() + sizeof(uint32_t) + header_size, payload_size);
	}

	// Create message
	DEBUG_PRINT("deserialized message, header_ptr: " << header << ", buffer_size: " << buffer.size());
	return std::optional<Message>(Message(header, buffer.data(), header->partial_frame_id));
}

std::optional<Message> RemoteMessageBroker::GetCurrentMessage(std::string_view topic)
{
	DEBUG_PRINT("topic: " << topic << ", IsLocalTopic: " << IsLocalTopic(topic));
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		DEBUG_PRINT("delegating to local broker");
		return m_LocalBroker->GetCurrentMessage(topic);
	}
	else
	{
		std::string machine = GetMachineFromTopic(topic_str);
		DEBUG_PRINT("remote machine: " << machine);
		Client& client = GetClientForMachine(machine);

		// Send GET_CURRENT request
		DEBUG_PRINT("sending GET_CURRENT request...");
		std::string response = client.MakeRequest("GET_CURRENT", topic_str);
		DEBUG_PRINT("response received, size: " << response.size());

		// Deserialize response
		std::vector<uint8_t> buffer;
		auto result = DeserializeMessage(response, buffer);
		DEBUG_PRINT("deserialized has_value: " << result.has_value());
		return result;
	}
}

std::optional<Message> RemoteMessageBroker::GetNextMessage(std::string_view topic,
                                                           size_t preferred_next_frame_id,
                                                           MessageSubscriptionMode mode,
                                                           double timeout_in_seconds,
                                                           EventWaitMethod wait_type,
                                                           void (*error_check)())
{
	(void)wait_type;
	(void)error_check;

	DEBUG_PRINT("topic: " << topic << ", frame_id: " << preferred_next_frame_id << ", mode: " << (mode == MessageSubscriptionMode::NewestOnly ? "NewestOnly" : "Sequential") << ", timeout: " << timeout_in_seconds);
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		DEBUG_PRINT("delegating to local broker");
		return m_LocalBroker->GetNextMessage(topic, preferred_next_frame_id, mode,
		                                      timeout_in_seconds, wait_type, error_check);
	}
	else
	{
		std::string machine = GetMachineFromTopic(topic_str);
		DEBUG_PRINT("remote machine: " << machine);
		Client& client = GetClientForMachine(machine);

		// Serialize request
		int mode_int = (mode == MessageSubscriptionMode::NewestOnly) ? 0 : 1;
		std::string request = SerializeGetNextRequest(topic_str, preferred_next_frame_id,
		                                               mode_int, timeout_in_seconds);

		// Send GET_NEXT request
		DEBUG_PRINT("sending GET_NEXT request...");
		std::string response = client.MakeRequest("GET_NEXT", request);
		DEBUG_PRINT("response received, size: " << response.size());

		// Deserialize response
		std::vector<uint8_t> buffer;
		auto result = DeserializeMessage(response, buffer);
		DEBUG_PRINT("deserialized has_value: " << result.has_value());
		return result;
	}
}

std::optional<Message> RemoteMessageBroker::TryGetNextMessage(std::string_view topic,
                                                               size_t preferred_next_frame_id,
                                                               MessageSubscriptionMode mode)
{
	DEBUG_PRINT("topic: " << topic << ", frame_id: " << preferred_next_frame_id << ", mode: " << (mode == MessageSubscriptionMode::NewestOnly ? "NewestOnly" : "Sequential"));
	return GetNextMessage(topic, preferred_next_frame_id, mode, 0.0);
}

std::vector<std::string> RemoteMessageBroker::GetAllMessageTopics()
{
	DEBUG_PRINT("called");
	// For now, just return local topics
	// In a full implementation, we'd query all peers
	auto topics = m_LocalBroker->GetAllMessageTopics();
	DEBUG_PRINT("got " << topics.size() << " topics from local broker");
	return topics;
}

double RemoteMessageBroker::GetMessageRate(std::string_view topic)
{
	DEBUG_PRINT("topic: " << topic << ", IsLocalTopic: " << IsLocalTopic(topic));
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		DEBUG_PRINT("delegating to local broker");
		double rate = m_LocalBroker->GetMessageRate(topic);
		DEBUG_PRINT("rate: " << rate);
		return rate;
	}
	else
	{
		std::string machine = GetMachineFromTopic(topic_str);
		DEBUG_PRINT("remote machine: " << machine);
		Client& client = GetClientForMachine(machine);

		DEBUG_PRINT("sending GET_RATE request...");
		std::string response = client.MakeRequest("GET_RATE", topic_str);
		DEBUG_PRINT("response: " << response);

		// Parse rate from string
		try
		{
			double rate = std::stod(response);
			DEBUG_PRINT("parsed rate: " << rate);
			return rate;
		}
		catch (...)
		{
			DEBUG_PRINT("failed to parse rate, returning 0.0");
			return 0.0;
		}
	}
}

bool RemoteMessageBroker::IsMessageAvailable(std::string_view topic, size_t frame_id)
{
	DEBUG_PRINT("topic: " << topic << ", frame_id: " << frame_id << ", IsLocalTopic: " << IsLocalTopic(topic));
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		bool available = m_LocalBroker->IsMessageAvailable(topic, frame_id);
		DEBUG_PRINT("local broker result: " << available);
		return available;
	}
	else
	{
		DEBUG_PRINT("remote topic, returning false (not implemented)");
		return false;
	}
}

bool RemoteMessageBroker::WillMessageBeAvailable(std::string_view topic, size_t frame_id)
{
	DEBUG_PRINT("topic: " << topic << ", frame_id: " << frame_id << ", IsLocalTopic: " << IsLocalTopic(topic));
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		bool available = m_LocalBroker->WillMessageBeAvailable(topic, frame_id);
		DEBUG_PRINT("local broker result: " << available);
		return available;
	}
	else
	{
		DEBUG_PRINT("remote topic, returning false (not implemented)");
		return false;
	}
}

size_t RemoteMessageBroker::GetNewestMessageId(std::string_view topic)
{
	DEBUG_PRINT("topic: " << topic << ", IsLocalTopic: " << IsLocalTopic(topic));
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		size_t id = m_LocalBroker->GetNewestMessageId(topic);
		DEBUG_PRINT("local broker result: " << id);
		return id;
	}
	else
	{
		DEBUG_PRINT("remote topic, returning 0 (not implemented)");
		return 0;
	}
}

size_t RemoteMessageBroker::GetOldestMessageId(std::string_view topic)
{
	DEBUG_PRINT("topic: " << topic << ", IsLocalTopic: " << IsLocalTopic(topic));
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		size_t id = m_LocalBroker->GetOldestMessageId(topic);
		DEBUG_PRINT("local broker result: " << id);
		return id;
	}
	else
	{
		DEBUG_PRINT("remote topic, returning 0 (not implemented)");
		return 0;
	}
}

// =============================================================================
// RemoteBrokerServer Implementation
// =============================================================================

RemoteBrokerServer::RemoteBrokerServer(std::shared_ptr<MessageBroker> broker, uint16_t port, int num_workers)
	: m_Broker(broker), m_Server(port, num_workers)
{
	DEBUG_PRINT("broker ptr: " << m_Broker.get() << ", port: " << port << ", workers: " << num_workers);

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
	DEBUG_PRINT("starting server");
	m_Server.Start();
	DEBUG_PRINT("server started");
}

void RemoteBrokerServer::Stop()
{
	DEBUG_PRINT("stopping server");
	m_Server.Stop();
	DEBUG_PRINT("server stopped");
}

bool RemoteBrokerServer::IsRunning() const
{
	bool running = m_Server.IsRunning();
	DEBUG_PRINT("is running: " << running);
	return running;
}

std::string RemoteBrokerServer::HandlePublish(const std::string& request_data)
{
	DEBUG_PRINT("called - request_size: " << request_data.size());

	try
	{
		// Deserialize the message
		auto msg_opt = DeserializeMessage(request_data);
		DEBUG_PRINT("DeserializeMessage returned has_value: " << msg_opt.has_value());

		if (!msg_opt.has_value())
		{
			DEBUG_PRINT("DeserializeMessage failed");
			return "ERROR: Failed to deserialize message";
		}

		Message& msg = msg_opt.value();
		DEBUG_PRINT("Message topic: " << (msg.m_Header ? msg.m_Header->topic : "NULL"));
		DEBUG_PRINT("Message payload_size: " << msg.GetPayloadSize());
		DEBUG_PRINT("m_Broker ptr: " << m_Broker.get());
		DEBUG_PRINT("Memory block Id: " << (int) msg.m_Header->payload_info.memory_block_id);

		Message prepared_msg = m_Broker->PrepareMessage(msg.GetTopic(), msg.GetPayloadSize(), msg.m_Header->payload_info.memory_block_id);

		DEBUG_PRINT("Prepared message.");

		std::memcpy(prepared_msg.GetPayload().data, msg.GetPayload().data, msg.GetPayloadSize());

		DEBUG_PRINT("Copied payload.");

		// Publish to local broker
		m_Broker->PublishMessage(prepared_msg, true);

		DEBUG_PRINT("PublishMessage completed successfully");
		return "OK";
	}
	catch (const std::exception& e)
	{
		ERROR_PRINT("Exception: " << e.what());
		return std::string("ERROR: ") + e.what();
	}
}

RemoteBrokerServer::GetNextParams RemoteBrokerServer::ParseGetNextRequest(const std::string& data)
{
	DEBUG_PRINT("parsing request data, size: " << data.size());
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

	DEBUG_PRINT("parsed: topic=" << params.topic << ", frame_id=" << params.preferred_frame_id << ", mode=" << (params.mode == MessageSubscriptionMode::NewestOnly ? "NewestOnly" : "Sequential") << ", timeout=" << params.timeout_seconds);
	return params;
}

std::string RemoteBrokerServer::HandleGetNext(const std::string& request_data)
{
	DEBUG_PRINT("called, request_size: " << request_data.size());
	try
	{
		// Parse request parameters
		GetNextParams params = ParseGetNextRequest(request_data);

		// Call GetNextMessage with timeout
		DEBUG_PRINT("calling GetNextMessage for topic: " << params.topic);
		auto msg_opt = m_Broker->GetNextMessage(params.topic, params.preferred_frame_id,
			params.mode, params.timeout_seconds);
		DEBUG_PRINT("GetNextMessage returned has_value: " << msg_opt.has_value());

		if (!msg_opt.has_value())
		{
			// Timeout - return empty response
			DEBUG_PRINT("no message available (timeout)");
			return "";
		}

		// Serialize and return the message
		std::string result = SerializeMessage(msg_opt.value());
		DEBUG_PRINT("serialized response size: " << result.size());
		return result;
	}
	catch (const std::exception& e)
	{
		ERROR_PRINT("exception: " << e.what());
		return std::string("ERROR: ") + e.what();
	}
}

std::string RemoteBrokerServer::HandleGetCurrent(const std::string& request_data)
{
	DEBUG_PRINT("topic: " << request_data);
	try
	{
		// request_data is just the topic string
		auto msg_opt = m_Broker->GetCurrentMessage(request_data);

		DEBUG_PRINT("has_value: " << msg_opt.has_value());

		if (!msg_opt.has_value())
		{
			// No message available - return empty response
			DEBUG_PRINT("no message available, returning empty");
			return "";
		}

		// Serialize and return the message
		std::string result = SerializeMessage(msg_opt.value());
		DEBUG_PRINT("serialized size: " << result.size());
		return result;
	}
	catch (const std::exception& e)
	{
		ERROR_PRINT("exception: " << e.what());
		return std::string("ERROR: ") + e.what();
	}
}

std::string RemoteBrokerServer::HandleGetRate(const std::string& request_data)
{
	DEBUG_PRINT("topic: " << request_data);
	try
	{
		// request_data is just the topic string
		DEBUG_PRINT("calling GetMessageRate");
		double rate = m_Broker->GetMessageRate(request_data);
		DEBUG_PRINT("rate: " << rate);

		// Convert to string
		return std::to_string(rate);
	}
	catch (const std::exception& e)
	{
		ERROR_PRINT("exception: " << e.what());
		return std::string("ERROR: ") + e.what();
	}
}

std::string RemoteBrokerServer::HandleListTopics(const std::string& request_data)
{
	(void)request_data; // Unused
	DEBUG_PRINT("called");

	try
	{
		DEBUG_PRINT("calling GetAllMessageTopics");
		std::vector<std::string> topics = m_Broker->GetAllMessageTopics();
		DEBUG_PRINT("got " << topics.size() << " topics");

		// Format as comma-separated list
		std::string result;
		for (size_t i = 0; i < topics.size(); ++i)
		{
			if (i > 0) result += ",";
			result += topics[i];
		}

		DEBUG_PRINT("returning topic list");
		return result;
	}
	catch (const std::exception& e)
	{
		ERROR_PRINT("exception: " << e.what());
		return std::string("ERROR: ") + e.what();
	}
}

std::string RemoteBrokerServer::SerializeMessage(const Message& msg)
{
	DEBUG_PRINT("called, header_ptr: " << msg.m_Header << ", payload_ptr: " << msg.m_Payload);
	// Serialize MessageHeader and payload into a string
	// Format: [topic][payload_size][memory_block_id][payload]
	// Must match RemoteMessageBroker::SerializeMessage format

	const size_t TOPIC_OFFSET = 0;
	const size_t PAYLOAD_SIZE_OFFSET = TOPIC_MAX_KEY_SIZE;
	const size_t MEMORY_BLOCK_ID_OFFSET = TOPIC_MAX_KEY_SIZE + sizeof(uint64_t);
	const size_t PAYLOAD_OFFSET = TOPIC_MAX_KEY_SIZE + sizeof(uint64_t) + sizeof(uint8_t);

	// Safety check - header should never be null
	if (!msg.m_Header)
	{
		throw std::runtime_error("Cannot serialize message with null header");
	}

	const MessageHeader* header = msg.m_Header;
	size_t payload_size = msg.GetPayloadSize();

	std::string result;
	result.resize(PAYLOAD_OFFSET + payload_size);

	std::memcpy(&result[TOPIC_OFFSET], header->topic, TOPIC_MAX_KEY_SIZE);
	std::memcpy(&result[PAYLOAD_SIZE_OFFSET], &payload_size, sizeof(uint64_t));
	std::memcpy(&result[MEMORY_BLOCK_ID_OFFSET], &header->payload_info.memory_block_id, sizeof(uint8_t));

	if (payload_size > 0 && msg.m_Payload)
	{
		std::memcpy(&result[PAYLOAD_OFFSET], msg.m_Payload, payload_size);
	}

	return result;
}

std::optional<Message> RemoteBrokerServer::DeserializeMessage(const std::string& data)
{
	DEBUG_PRINT("called, data_size: " << data.size());

	if (data.empty())
	{
		return std::nullopt;
	}

	// Deserialize from format: [topic][payload_size][memory_block_id][payload]
	// Must match RemoteMessageBroker::SerializeMessage format
	const size_t TOPIC_OFFSET = 0;
	const size_t PAYLOAD_SIZE_OFFSET = TOPIC_MAX_KEY_SIZE;
	const size_t MEMORY_BLOCK_ID_OFFSET = TOPIC_MAX_KEY_SIZE + sizeof(uint64_t);
	const size_t PAYLOAD_OFFSET = TOPIC_MAX_KEY_SIZE + sizeof(uint64_t) + sizeof(uint8_t);

	// Check minimum size (header fields + at least empty payload)
	if (data.length() < PAYLOAD_OFFSET)
	{
		return std::nullopt;
	}

	// Read payload size
	uint64_t payload_size;
	std::memcpy(&payload_size, data.data() + PAYLOAD_SIZE_OFFSET, sizeof(uint64_t));

	// Check total size matches
	if (data.length() != PAYLOAD_OFFSET + payload_size)
	{
		return std::nullopt;
	}

	// Allocate header on heap
	MessageHeader* header = new MessageHeader();
	std::memset(header, 0, sizeof(MessageHeader));

	// Read topic
	std::memcpy(header->topic, data.data() + TOPIC_OFFSET, TOPIC_MAX_KEY_SIZE);

	// Read memory block ID
	uint8_t memory_block_id;
	std::memcpy(&memory_block_id, data.data() + MEMORY_BLOCK_ID_OFFSET, sizeof(uint8_t));

	// Set payload info
	header->payload_info.total_size = payload_size;
	header->payload_info.memory_block_id = memory_block_id;
	header->payload_info.offset_in_buffer = 0;

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
		std::memcpy(payload, data.data() + PAYLOAD_OFFSET, payload_size);
	}

	// Create message
	// Note: The caller takes ownership of the header and payload memory
	DEBUG_PRINT("deserialized message, topic: " << header->topic << ", payload_size: " << payload_size << ", memory_block_id: " << (int)memory_block_id);
	return std::optional<Message>(Message(header, payload, 0));
}
