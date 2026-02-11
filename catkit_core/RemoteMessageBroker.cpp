#include "RemoteMessageBroker.h"
#include "LocalMessageBroker.h"

#include <cstring>
#include <sstream>
#include <stdexcept>
#include <optional>

RemoteMessageBroker::RemoteMessageBroker(std::shared_ptr<LocalMessageBroker> local_broker,
                                          const std::string& local_machine_name,
                                          const std::vector<PeerConfig>& peers)
	: m_LocalBroker(local_broker), m_LocalMachineName(local_machine_name)
{
	// Create Client objects for each peer
	for (const auto& peer : peers)
	{
		m_PeerClients[peer.name] = std::make_unique<Client>(peer.host, peer.port);
	}
}

RemoteMessageBroker::~RemoteMessageBroker()
{
	// Temporary buffers are automatically cleaned up by unordered_map destructor
}

bool RemoteMessageBroker::IsLocalTopic(std::string_view topic)
{
	// Check if topic starts with local machine name followed by '/'
	std::string prefix = m_LocalMachineName + "/";
	return topic.substr(0, prefix.length()) == prefix;
}

std::string RemoteMessageBroker::GetMachineFromTopic(std::string_view topic)
{
	// Extract machine name (everything before first '/')
	size_t slash_pos = topic.find('/');
	if (slash_pos == std::string_view::npos)
	{
		return std::string(topic);  // No slash, entire topic is machine name
	}
	return std::string(topic.substr(0, slash_pos));
}

Client& RemoteMessageBroker::GetClientForMachine(const std::string& machine)
{
	auto it = m_PeerClients.find(machine);
	if (it == m_PeerClients.end())
	{
		throw std::runtime_error("Unknown peer: " + machine);
	}
	return *(it->second);
}

Message RemoteMessageBroker::PrepareMessageImpl(std::string_view topic, size_t payload_size,
                                                Uuid trace_id, uint8_t memory_block_id)
{
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
	// Format: [header_size (4 bytes)][MessageHeader][payload]

	// Safety check - header should never be null
	if (!msg.m_Header)
	{
		throw std::runtime_error("Cannot serialize message with null header");
	}

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

Message RemoteMessageBroker::PublishMessage(Message message, bool is_final)
{
	std::string topic(message.GetTopic());

	if (IsLocalTopic(topic))
	{
		// Local topic: delegate to LocalMessageBroker
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
		Client& client = GetClientForMachine(machine);

		// Serialize the message
		std::string serialized = SerializeMessage(message);

		// Send to remote
		std::string response = client.MakeRequest("PUBLISH", serialized);

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
	return std::optional<Message>(Message(header, buffer.data(), header->partial_frame_id));
}

std::optional<Message> RemoteMessageBroker::GetCurrentMessage(std::string_view topic)
{
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		return m_LocalBroker->GetCurrentMessage(topic);
	}
	else
	{
		std::string machine = GetMachineFromTopic(topic_str);
		Client& client = GetClientForMachine(machine);

		// Send GET_CURRENT request
		std::string response = client.MakeRequest("GET_CURRENT", topic_str);

		// Deserialize response
		std::vector<uint8_t> buffer;
		return DeserializeMessage(response, buffer);
	}
}

std::optional<Message> RemoteMessageBroker::GetNextMessage(std::string_view topic,
                                                           size_t preferred_next_frame_id,
                                                           MessageSubscriptionMode mode,
                                                           double timeout_in_seconds,
                                                           EventWaitMethod wait_type,
                                                           void (*error_check)())
{
	(void)wait_type;  // Not used for remote
	(void)error_check;  // Not used for remote

	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		return m_LocalBroker->GetNextMessage(topic, preferred_next_frame_id, mode,
		                                      timeout_in_seconds, wait_type, error_check);
	}
	else
	{
		std::string machine = GetMachineFromTopic(topic_str);
		Client& client = GetClientForMachine(machine);

		// Serialize request
		int mode_int = (mode == MessageSubscriptionMode::NewestOnly) ? 0 : 1;
		std::string request = SerializeGetNextRequest(topic_str, preferred_next_frame_id,
		                                               mode_int, timeout_in_seconds);

		// Send GET_NEXT request
		std::string response = client.MakeRequest("GET_NEXT", request);

		// Deserialize response
		std::vector<uint8_t> buffer;
		return DeserializeMessage(response, buffer);
	}
}

std::optional<Message> RemoteMessageBroker::TryGetNextMessage(std::string_view topic,
                                                               size_t preferred_next_frame_id,
                                                               MessageSubscriptionMode mode)
{
	return GetNextMessage(topic, preferred_next_frame_id, mode, 0.0);
}

std::vector<std::string> RemoteMessageBroker::GetAllMessageTopics()
{
	// For now, just return local topics
	// In a full implementation, we'd query all peers
	return m_LocalBroker->GetAllMessageTopics();
}

double RemoteMessageBroker::GetMessageRate(std::string_view topic)
{
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		return m_LocalBroker->GetMessageRate(topic);
	}
	else
	{
		std::string machine = GetMachineFromTopic(topic_str);
		Client& client = GetClientForMachine(machine);

		std::string response = client.MakeRequest("GET_RATE", topic_str);

		// Parse rate from string
		try
		{
			return std::stod(response);
		}
		catch (...)
		{
			return 0.0;
		}
	}
}

bool RemoteMessageBroker::IsMessageAvailable(std::string_view topic, size_t frame_id)
{
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		return m_LocalBroker->IsMessageAvailable(topic, frame_id);
	}
	else
	{
		// For remote topics, we'd need to query the remote broker
		// For now, return false as a safe default
		return false;
	}
}

bool RemoteMessageBroker::WillMessageBeAvailable(std::string_view topic, size_t frame_id)
{
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		return m_LocalBroker->WillMessageBeAvailable(topic, frame_id);
	}
	else
	{
		// For remote topics, we'd need to query the remote broker
		// For now, return false as a safe default
		return false;
	}
}

size_t RemoteMessageBroker::GetNewestMessageId(std::string_view topic)
{
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		return m_LocalBroker->GetNewestMessageId(topic);
	}
	else
	{
		// For remote topics, we'd need to query the remote broker
		// For now, return 0 as a safe default
		return 0;
	}
}

size_t RemoteMessageBroker::GetOldestMessageId(std::string_view topic)
{
	std::string topic_str(topic);

	if (IsLocalTopic(topic_str))
	{
		return m_LocalBroker->GetOldestMessageId(topic);
	}
	else
	{
		// For remote topics, we'd need to query the remote broker
		// For now, return 0 as a safe default
		return 0;
	}
}
