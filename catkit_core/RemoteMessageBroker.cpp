#include "RemoteMessageBroker.h"
#include "LocalMessageBroker.h"

#include <cstring>
#include <sstream>
#include <stdexcept>
#include <optional>
#include <iostream>

#define DEBUG_PRINT(msg) std::cerr << "[DEBUG] " << __func__ << ":" << __LINE__ << " - " << msg << std::endl
#define ERROR_PRINT(msg) std::cerr << "[ERROR] " << __func__ << ":" << __LINE__ << " - " << msg << std::endl

struct PublishMsg
{
    // Data fields
    char topic[TOPIC_MAX_KEY_SIZE];
    uint64_t payload_size;
    uint8_t memory_block_id;
    const void* payload;

    static size_t GetSize(uint64_t payload_size)
    {
        return TOPIC_MAX_KEY_SIZE + sizeof(uint64_t) + sizeof(uint8_t) + payload_size;
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        size_t required_size = GetSize(payload_size);
        if (buffer_size < required_size) return false;

        char* buf = static_cast<char*>(buffer);
        size_t offset = 0;

        // Write topic (pad with zeros)
        std::memcpy(buf + offset, topic, TOPIC_MAX_KEY_SIZE);
        offset += TOPIC_MAX_KEY_SIZE;

        // Write payload_size
        std::memcpy(buf + offset, &payload_size, sizeof(uint64_t));
        offset += sizeof(uint64_t);

        // Write memory_block_id
        std::memcpy(buf + offset, &memory_block_id, sizeof(uint8_t));
        offset += sizeof(uint8_t);

        // Write payload (copy from external buffer)
        if (payload_size > 0)
        {
            std::memcpy(buf + offset, payload, payload_size);
        }

        return true;
    }

    static PublishMsg Deserialize(const void* data, size_t data_size)
    {
        PublishMsg msg;
        const char* buf = static_cast<const char*>(data);
        size_t offset = 0;

        // Read topic
        std::memcpy(msg.topic, buf + offset, TOPIC_MAX_KEY_SIZE);
        msg.topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';  // Ensure null-terminated
        offset += TOPIC_MAX_KEY_SIZE;

        // Read payload_size
        std::memcpy(&msg.payload_size, buf + offset, sizeof(uint64_t));
        offset += sizeof(uint64_t);

        // Read memory_block_id
        std::memcpy(&msg.memory_block_id, buf + offset, sizeof(uint8_t));
        offset += sizeof(uint8_t);

        // Payload points into data buffer (zero-copy)
        msg.payload = (msg.payload_size > 0) ? (buf + offset) : nullptr;

        return msg;
    }
};

struct GetNextRequestMsg
{
    // Data fields
    char topic[TOPIC_MAX_KEY_SIZE];
    uint64_t frame_id;
    uint8_t mode;
    double timeout;

    static const size_t TOTAL_SIZE = TOPIC_MAX_KEY_SIZE + sizeof(uint64_t) + sizeof(uint8_t) + sizeof(double);

    static size_t GetSize()
    {
        return TOTAL_SIZE;
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        if (buffer_size < TOTAL_SIZE) return false;

        char* buf = static_cast<char*>(buffer);
        size_t offset = 0;

        std::memcpy(buf + offset, topic, TOPIC_MAX_KEY_SIZE);
        offset += TOPIC_MAX_KEY_SIZE;

        std::memcpy(buf + offset, &frame_id, sizeof(uint64_t));
        offset += sizeof(uint64_t);

        std::memcpy(buf + offset, &mode, sizeof(uint8_t));
        offset += sizeof(uint8_t);

        std::memcpy(buf + offset, &timeout, sizeof(double));

        return true;
    }

    static GetNextRequestMsg Deserialize(const void* data, size_t data_size)
    {
        GetNextRequestMsg msg;
        const char* buf = static_cast<const char*>(data);
        size_t offset = 0;

        std::memcpy(msg.topic, buf + offset, TOPIC_MAX_KEY_SIZE);
        msg.topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';
        offset += TOPIC_MAX_KEY_SIZE;

        std::memcpy(&msg.frame_id, buf + offset, sizeof(uint64_t));
        offset += sizeof(uint64_t);

        std::memcpy(&msg.mode, buf + offset, sizeof(uint8_t));
        offset += sizeof(uint8_t);

        std::memcpy(&msg.timeout, buf + offset, sizeof(double));

        return msg;
    }
};

struct GetNextResponseMsg
{
    // Data fields
    uint8_t has_message;
    PublishMsg message;  // Only valid if has_message == 1

    static size_t GetSize(uint64_t payload_size)
    {
        return sizeof(uint8_t) + (payload_size > 0 ? PublishMsg::GetSize(payload_size) : 0);
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        if (buffer_size < sizeof(uint8_t)) return false;

        char* buf = static_cast<char*>(buffer);
        std::memcpy(buf, &has_message, sizeof(uint8_t));

        if (has_message && message.payload_size > 0)
        {
            return message.Serialize(buf + sizeof(uint8_t), buffer_size - sizeof(uint8_t));
        }

        return true;
    }

    static GetNextResponseMsg Deserialize(const void* data, size_t data_size)
    {
        GetNextResponseMsg msg;
        const char* buf = static_cast<const char*>(data);

        std::memcpy(&msg.has_message, buf, sizeof(uint8_t));

        if (msg.has_message && data_size > sizeof(uint8_t))
        {
            msg.message = PublishMsg::Deserialize(buf + sizeof(uint8_t), data_size - sizeof(uint8_t));
        }

        return msg;
    }
};

struct GetCurrentRequestMsg
{
    char topic[TOPIC_MAX_KEY_SIZE];

    static const size_t TOTAL_SIZE = TOPIC_MAX_KEY_SIZE;

    static size_t GetSize()
    {
        return TOTAL_SIZE;
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        if (buffer_size < TOTAL_SIZE) return false;
        std::memcpy(buffer, topic, TOPIC_MAX_KEY_SIZE);
        return true;
    }

    static GetCurrentRequestMsg Deserialize(const void* data, size_t data_size)
    {
        GetCurrentRequestMsg msg;
        std::memcpy(msg.topic, data, TOPIC_MAX_KEY_SIZE);
        msg.topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';
        return msg;
    }
};

using GetCurrentResponseMsg = GetNextResponseMsg;

struct GetRateRequestMsg
{
    char topic[TOPIC_MAX_KEY_SIZE];

    static const size_t TOTAL_SIZE = TOPIC_MAX_KEY_SIZE;

    static size_t GetSize()
    {
        return TOTAL_SIZE;
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        if (buffer_size < TOTAL_SIZE) return false;
        std::memcpy(buffer, topic, TOPIC_MAX_KEY_SIZE);
        return true;
    }

    static GetRateRequestMsg Deserialize(const void* data, size_t data_size)
    {
        GetRateRequestMsg msg;
        std::memcpy(msg.topic, data, TOPIC_MAX_KEY_SIZE);
        msg.topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';
        return msg;
    }
};

struct GetRateResponseMsg
{
    double rate;

    static const size_t TOTAL_SIZE = sizeof(double);

    static size_t GetSize()
    {
        return TOTAL_SIZE;
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        if (buffer_size < TOTAL_SIZE) return false;
        std::memcpy(buffer, &rate, sizeof(double));
        return true;
    }

    static GetRateResponseMsg Deserialize(const void* data, size_t data_size)
    {
        GetRateResponseMsg msg;
        std::memcpy(&msg.rate, data, sizeof(double));
        return msg;
    }
};

struct ListTopicsRequestMsg
{
    static size_t GetSize()
    {
        return 0;  // Nothing to serialize
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        return true;  // Nothing to serialize
    }

    static ListTopicsRequestMsg Deserialize(const void* data, size_t data_size)
    {
        return ListTopicsRequestMsg();
    }
};

struct ListTopicsResponseMsg
{
    uint32_t num_topics;
    std::vector<std::pair<uint32_t, const char*> > topics;  // (length, data) pairs - zero-copy

    static size_t GetSize(const std::vector<std::string>& topics)
    {
        size_t size = sizeof(uint32_t);  // num_topics
        for (const auto& topic : topics)
        {
            size += sizeof(uint32_t) + topic.length();  // length prefix + topic
        }
        return size;
    }

    bool Serialize(void* buffer, size_t buffer_size, const std::vector<std::string>& topics) const
    {
        size_t required_size = GetSize(topics);
        if (buffer_size < required_size) return false;

        char* buf = static_cast<char*>(buffer);
        size_t offset = 0;

        // Write num_topics
        uint32_t num = static_cast<uint32_t>(topics.size());
        std::memcpy(buf + offset, &num, sizeof(uint32_t));
        offset += sizeof(uint32_t);

        // Write each topic
        for (const auto& topic : topics)
        {
            uint32_t len = static_cast<uint32_t>(topic.length());
            std::memcpy(buf + offset, &len, sizeof(uint32_t));
            offset += sizeof(uint32_t);
            std::memcpy(buf + offset, topic.data(), len);
            offset += len;
        }

        return true;
    }

    static ListTopicsResponseMsg Deserialize(const void* data, size_t data_size)
    {
        ListTopicsResponseMsg msg;
        const char* buf = static_cast<const char*>(data);
        size_t offset = 0;

        // Read num_topics
        std::memcpy(&msg.num_topics, buf + offset, sizeof(uint32_t));
        offset += sizeof(uint32_t);

        // Read each topic (zero-copy pointers)
        for (uint32_t i = 0; i < msg.num_topics && offset < data_size; i++)
        {
            uint32_t len;
            std::memcpy(&len, buf + offset, sizeof(uint32_t));
            offset += sizeof(uint32_t);

            if (offset + len <= data_size)
            {
                msg.topics.emplace_back(len, buf + offset);
                offset += len;
            }
        }

        return msg;
    }
};

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

	// Safety check - header should never be null
	if (!msg.m_Header)
	{
		throw std::runtime_error("Cannot serialize message with null header");
	}

	const MessageHeader &header = *msg.m_Header;
	size_t payload_size = msg.GetPayloadSize();

	// Create message struct
	PublishMsg pub_msg;
	std::strncpy(pub_msg.topic, msg.GetTopic().data(), TOPIC_MAX_KEY_SIZE - 1);
	pub_msg.topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';
	pub_msg.payload_size = payload_size;
	pub_msg.memory_block_id = header.payload_info.memory_block_id;
	pub_msg.payload = msg.GetPayload().data;

	// Allocate buffer and serialize
	std::string result;
	result.resize(PublishMsg::GetSize(payload_size));
	if (!pub_msg.Serialize(&result[0], result.size()))
	{
		throw std::runtime_error("Failed to serialize message");
	}

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

	// Create message struct
	GetNextRequestMsg msg;
	std::strncpy(msg.topic, topic.data(), TOPIC_MAX_KEY_SIZE - 1);
	msg.topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';
	msg.frame_id = frame_id;
	msg.mode = static_cast<uint8_t>(mode);
	msg.timeout = timeout;

	// Allocate buffer and serialize
	std::string result;
	result.resize(GetNextRequestMsg::GetSize());
	if (!msg.Serialize(&result[0], result.size()))
	{
		throw std::runtime_error("Failed to serialize GetNextRequest");
	}

	DEBUG_PRINT("serialized size: " << result.size());
	return result;
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

		// Serialize GET_CURRENT request
		GetCurrentRequestMsg req;
		std::strncpy(req.topic, topic_str.data(), TOPIC_MAX_KEY_SIZE - 1);
		req.topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';

		std::string request_data;
		request_data.resize(GetCurrentRequestMsg::GetSize());
		if (!req.Serialize(&request_data[0], request_data.size()))
		{
			throw std::runtime_error("Failed to serialize GetCurrentRequest");
		}

		DEBUG_PRINT("sending GET_CURRENT request...");
		std::string response = client.MakeRequest("GET_CURRENT", request_data);
		DEBUG_PRINT("response received, size: " << response.size());

		// Parse response
		GetCurrentResponseMsg resp = GetCurrentResponseMsg::Deserialize(response.data(), response.size());

		if (!resp.has_message)
		{
			DEBUG_PRINT("no message in response");
			return std::nullopt;
		}

		// Convert PublishMsg to Message
		MessageHeader* header = new MessageHeader();
		std::memset(header, 0, sizeof(MessageHeader));
		std::memcpy(header->topic, resp.message.topic, TOPIC_MAX_KEY_SIZE);
		header->payload_info.total_size = resp.message.payload_size;
		header->payload_info.memory_block_id = resp.message.memory_block_id;
		header->payload_info.offset_in_buffer = 0;

		void* payload = std::malloc(resp.message.payload_size);
		if (resp.message.payload_size > 0 && resp.message.payload)
		{
			std::memcpy(payload, resp.message.payload, resp.message.payload_size);
		}

		DEBUG_PRINT("deserialized message, payload_size: " << resp.message.payload_size);
		return std::optional<Message>(Message(header, payload, 0));
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

		// Parse response
		GetNextResponseMsg resp = GetNextResponseMsg::Deserialize(response.data(), response.size());

		if (!resp.has_message)
		{
			DEBUG_PRINT("no message in response");
			return std::nullopt;
		}

		// Convert PublishMsg to Message
		MessageHeader* header = new MessageHeader();
		std::memset(header, 0, sizeof(MessageHeader));
		std::memcpy(header->topic, resp.message.topic, TOPIC_MAX_KEY_SIZE);
		header->payload_info.total_size = resp.message.payload_size;
		header->payload_info.memory_block_id = resp.message.memory_block_id;
		header->payload_info.offset_in_buffer = 0;

		void* payload = std::malloc(resp.message.payload_size);
		if (resp.message.payload_size > 0 && resp.message.payload)
		{
			std::memcpy(payload, resp.message.payload, resp.message.payload_size);
		}

		DEBUG_PRINT("deserialized message, payload_size: " << resp.message.payload_size);
		return std::optional<Message>(Message(header, payload, 0));
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

		// Serialize GET_RATE request
		GetRateRequestMsg req;
		std::strncpy(req.topic, topic_str.data(), TOPIC_MAX_KEY_SIZE - 1);
		req.topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';

		std::string request_data;
		request_data.resize(GetRateRequestMsg::GetSize());
		if (!req.Serialize(&request_data[0], request_data.size()))
		{
			throw std::runtime_error("Failed to serialize GetRateRequest");
		}

		DEBUG_PRINT("sending GET_RATE request...");
		std::string response = client.MakeRequest("GET_RATE", request_data);
		DEBUG_PRINT("response size: " << response.size());

		// Parse rate from binary response
		if (response.size() != GetRateResponseMsg::GetSize())
		{
			DEBUG_PRINT("invalid response size, returning 0.0");
			return 0.0;
		}

		GetRateResponseMsg resp = GetRateResponseMsg::Deserialize(response.data(), response.size());
		DEBUG_PRINT("parsed rate: " << resp.rate);
		return resp.rate;
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

RemoteBrokerServer::RemoteBrokerServer(std::shared_ptr<LocalMessageBroker> broker, uint16_t port, int num_workers)
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
		// Deserialize using the struct (zero-copy payload)
		PublishMsg msg = PublishMsg::Deserialize(request_data.data(), request_data.size());

		DEBUG_PRINT("Message topic: " << msg.topic);
		DEBUG_PRINT("Message payload_size: " << msg.payload_size);
        DEBUG_PRINT("Payload: " << msg.payload);
		DEBUG_PRINT("Memory block Id: " << (int)msg.memory_block_id);

		Message prepared_msg = m_Broker->PrepareMessage(msg.topic, msg.payload_size, (int) msg.memory_block_id);

		DEBUG_PRINT("Prepared message.");

        DEBUG_PRINT("Prepared message payload size: " << prepared_msg.GetPayloadInfo().total_size);
        DEBUG_PRINT("Prepared message block id: " << (int) prepared_msg.GetPayloadInfo().memory_block_id);

		// std::memcpy(prepared_msg.GetPayload().data, msg.payload, msg.payload_size);

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
	// Parse using the message struct
	GetNextRequestMsg msg = GetNextRequestMsg::Deserialize(data.data(), data.length());

	GetNextParams params;
	params.topic = std::string(msg.topic);
	params.preferred_frame_id = msg.frame_id;
	params.mode = (msg.mode == 0) ? MessageSubscriptionMode::NewestOnly : MessageSubscriptionMode::Sequential;
	params.timeout_seconds = msg.timeout;

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

		// Serialize response using struct
		GetNextResponseMsg resp;
		resp.has_message = msg_opt.has_value() ? 1 : 0;

		if (msg_opt.has_value())
		{
			Message& inner_msg = msg_opt.value();
			std::strncpy(resp.message.topic, inner_msg.GetTopic().data(), TOPIC_MAX_KEY_SIZE - 1);
			resp.message.topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';
			resp.message.payload_size = inner_msg.GetPayloadSize();
			resp.message.memory_block_id = inner_msg.m_Header ? inner_msg.m_Header->payload_info.memory_block_id : 0;
			resp.message.payload = inner_msg.GetPayload().data;
		}

		std::string result;
		result.resize(GetNextResponseMsg::GetSize(resp.has_message ? resp.message.payload_size : 0));
		if (!resp.Serialize(&result[0], result.size()))
		{
			return "ERROR: Failed to serialize response";
		}

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
	DEBUG_PRINT("request_size: " << request_data.size());
	try
	{
		// Parse binary format: [topic (TOPIC_MAX_KEY_SIZE)]
		if (request_data.size() != GetCurrentRequestMsg::TOTAL_SIZE)
		{
			ERROR_PRINT("invalid request size: " << request_data.size() << ", expected: " << GetCurrentRequestMsg::TOTAL_SIZE);
			return "ERROR: Invalid request size";
		}

		GetCurrentRequestMsg req = GetCurrentRequestMsg::Deserialize(request_data.data(), request_data.size());
		std::string topic(req.topic);
		DEBUG_PRINT("topic: " << topic);

		auto msg_opt = m_Broker->GetCurrentMessage(topic);

		DEBUG_PRINT("has_value: " << msg_opt.has_value());

		// Serialize response using struct
		GetCurrentResponseMsg resp;
		resp.has_message = msg_opt.has_value() ? 1 : 0;

		if (msg_opt.has_value())
		{
			Message& inner_msg = msg_opt.value();
			std::strncpy(resp.message.topic, inner_msg.GetTopic().data(), TOPIC_MAX_KEY_SIZE - 1);
			resp.message.topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';
			resp.message.payload_size = inner_msg.GetPayloadSize();
			resp.message.memory_block_id = inner_msg.m_Header ? inner_msg.m_Header->payload_info.memory_block_id : 0;
			resp.message.payload = inner_msg.GetPayload().data;
		}

		std::string result;
		result.resize(GetCurrentResponseMsg::GetSize(resp.has_message ? resp.message.payload_size : 0));
		if (!resp.Serialize(&result[0], result.size()))
		{
			return "ERROR: Failed to serialize response";
		}

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
	DEBUG_PRINT("request_size: " << request_data.size());
	try
	{
		// Parse request using struct
		GetRateRequestMsg req = GetRateRequestMsg::Deserialize(request_data.data(), request_data.size());
		std::string topic(req.topic);
		DEBUG_PRINT("topic: " << topic);

		DEBUG_PRINT("calling GetMessageRate");
		double rate = m_Broker->GetMessageRate(topic);
		DEBUG_PRINT("rate: " << rate);

		// Return response using struct
		GetRateResponseMsg resp;
		resp.rate = rate;

		std::string result;
		result.resize(GetRateResponseMsg::GetSize());
		if (!resp.Serialize(&result[0], result.size()))
		{
			return "ERROR: Failed to serialize response";
		}
		return result;
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
