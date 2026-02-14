#include "RemoteMessageBroker.h"
#include "LocalMessageBroker.h"
#include "ArrayView.h"
#include "Timing.h"

#include <cstring>
#include <sstream>
#include <stdexcept>
#include <optional>
#include <iostream>
#include <algorithm>

#define DEBUG_PRINT(msg) std::cerr << "[DEBUG] " << __func__ << ":" << __LINE__ << " - " << msg << std::endl
#define ERROR_PRINT(msg) std::cerr << "[ERROR] " << __func__ << ":" << __LINE__ << " - " << msg << std::endl

// PUBLISH message format:
// [topic_length (1 byte)][topic (variable)][payload_size (8 bytes)][memory_block_id (1 byte)][array_info][payload (variable)]
// Payload is zero-copy - points into external buffer
struct PublishMsg
{
    // Data fields
    std::string topic;
    uint64_t payload_size;
    uint8_t memory_block_id;
    ArrayInfo array_info;
    const void* payload;

    // Get serialized size of this message
    size_t GetSize() const
    {
        size_t size = sizeof(uint8_t) + topic.length() + sizeof(uint64_t) + sizeof(uint8_t);
        size += sizeof(char) + sizeof(char) + sizeof(uint8_t) + sizeof(uint8_t);
        size += MAX_NUM_DIMENSIONS * sizeof(uint32_t) * 2;  // shape + strides
        size += payload_size;
        return size;
    }

    // Serialize into pre-allocated buffer
    // Returns false if buffer too small.
    bool Serialize(void* buffer, size_t buffer_size) const
    {
        size_t required_size = GetSize();
        if (buffer_size < required_size) return false;

        char* buf = static_cast<char*>(buffer);
        size_t offset = 0;

        // Write topic [length (1 byte)][string bytes]
        uint8_t topic_len = static_cast<uint8_t>(topic.length());
        std::memcpy(buf + offset, &topic_len, sizeof(uint8_t));
        offset += sizeof(uint8_t);
        std::memcpy(buf + offset, topic.data(), topic_len);
        offset += topic_len;

        // Write payload_size
        std::memcpy(buf + offset, &payload_size, sizeof(uint64_t));
        offset += sizeof(uint64_t);

        // Write memory_block_id
        std::memcpy(buf + offset, &memory_block_id, sizeof(uint8_t));
        offset += sizeof(uint8_t);

        // Write array_info
        std::memcpy(buf + offset, &array_info.data_type, sizeof(char));
        offset += sizeof(char);
        std::memcpy(buf + offset, &array_info.byte_order, sizeof(char));
        offset += sizeof(char);
        std::memcpy(buf + offset, &array_info.item_size, sizeof(uint8_t));
        offset += sizeof(uint8_t);
        std::memcpy(buf + offset, &array_info.ndim, sizeof(uint8_t));
        offset += sizeof(uint8_t);
        std::memcpy(buf + offset, array_info.shape.data(), MAX_NUM_DIMENSIONS * sizeof(uint32_t));
        offset += MAX_NUM_DIMENSIONS * sizeof(uint32_t);
        std::memcpy(buf + offset, array_info.strides.data(), MAX_NUM_DIMENSIONS * sizeof(uint32_t));
        offset += MAX_NUM_DIMENSIONS * sizeof(uint32_t);

        // Write payload (copy from external buffer)
        if (payload_size > 0)
        {
            std::memcpy(buf + offset, payload, payload_size);
        }

        return true;
    }

    // Deserialize from buffer - payload points into data (zero-copy)
    // WARNING: data must remain valid as long as msg.payload is used
    static PublishMsg Deserialize(const void* data, size_t data_size)
    {
        PublishMsg msg;
        const char* buf = static_cast<const char*>(data);
        size_t offset = 0;

        // Read topic length
        uint8_t topic_len;
        std::memcpy(&topic_len, buf + offset, sizeof(uint8_t));
        offset += sizeof(uint8_t);

        // Read topic
        msg.topic = std::string(buf + offset, topic_len);
        offset += topic_len;

        // Read payload_size
        std::memcpy(&msg.payload_size, buf + offset, sizeof(uint64_t));
        offset += sizeof(uint64_t);

        // Read memory_block_id
        std::memcpy(&msg.memory_block_id, buf + offset, sizeof(uint8_t));
        offset += sizeof(uint8_t);

        // Read array_info
        std::memcpy(&msg.array_info.data_type, buf + offset, sizeof(char));
        offset += sizeof(char);
        std::memcpy(&msg.array_info.byte_order, buf + offset, sizeof(char));
        offset += sizeof(char);
        std::memcpy(&msg.array_info.item_size, buf + offset, sizeof(uint8_t));
        offset += sizeof(uint8_t);
        std::memcpy(&msg.array_info.ndim, buf + offset, sizeof(uint8_t));
        offset += sizeof(uint8_t);
        std::memcpy(msg.array_info.shape.data(), buf + offset, MAX_NUM_DIMENSIONS * sizeof(uint32_t));
        offset += MAX_NUM_DIMENSIONS * sizeof(uint32_t);
        std::memcpy(msg.array_info.strides.data(), buf + offset, MAX_NUM_DIMENSIONS * sizeof(uint32_t));
        offset += MAX_NUM_DIMENSIONS * sizeof(uint32_t);

        // Payload points into data buffer (zero-copy)
        msg.payload = (msg.payload_size > 0) ? (buf + offset) : nullptr;

        return msg;
    }
};

// GET_NEXT request format: [topic_length (1 byte)][topic (variable)][frame_id (8 bytes)][mode (1 byte)][timeout (8 bytes)]
struct GetNextRequestMsg
{
    // Data fields
    std::string topic;
    uint64_t frame_id;
    uint8_t mode;
    double timeout;

    // Get serialized size of this message
    size_t GetSize() const
    {
        return sizeof(uint8_t) + topic.length() + sizeof(uint64_t) + sizeof(uint8_t) + sizeof(double);
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        size_t required_size = GetSize();
        if (buffer_size < required_size) return false;

        char* buf = static_cast<char*>(buffer);
        size_t offset = 0;

        // Write topic [length (1 byte)][string bytes]
        uint8_t topic_len = static_cast<uint8_t>(topic.length());
        std::memcpy(buf + offset, &topic_len, sizeof(uint8_t));
        offset += sizeof(uint8_t);
        std::memcpy(buf + offset, topic.data(), topic_len);
        offset += topic_len;

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

        // Read topic length
        uint8_t topic_len;
        std::memcpy(&topic_len, buf + offset, sizeof(uint8_t));
        offset += sizeof(uint8_t);

        // Read topic
        msg.topic = std::string(buf + offset, topic_len);
        offset += topic_len;

        std::memcpy(&msg.frame_id, buf + offset, sizeof(uint64_t));
        offset += sizeof(uint64_t);

        std::memcpy(&msg.mode, buf + offset, sizeof(uint8_t));
        offset += sizeof(uint8_t);

        std::memcpy(&msg.timeout, buf + offset, sizeof(double));

        return msg;
    }
};

// GET_NEXT response format: [has_message (1 byte)][message if has_message==1]
// If has_message==1: [topic_length (1 byte)][topic (variable)][payload_size (8 bytes)][memory_block_id (1 byte)][payload (variable)]
// Payload is zero-copy
struct GetNextResponseMsg
{
    // Data fields
    uint8_t has_message;
    PublishMsg message;  // Only valid if has_message == 1

    // Get serialized size of this message
    size_t GetSize() const
    {
        return sizeof(uint8_t) + (has_message ? message.GetSize() : 0);
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        if (buffer_size < sizeof(uint8_t)) return false;

        char* buf = static_cast<char*>(buffer);
        std::memcpy(buf, &has_message, sizeof(uint8_t));

        if (has_message)
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

// GET_CURRENT request format: [topic_length (1 byte)][topic (variable)]
struct GetCurrentRequestMsg
{
    std::string topic;

    // Get serialized size of this message
    size_t GetSize() const
    {
        return sizeof(uint8_t) + topic.length();
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        size_t required_size = GetSize();
        if (buffer_size < required_size) return false;

        char* buf = static_cast<char*>(buffer);
        size_t offset = 0;

        // Write topic [length (1 byte)][string bytes]
        uint8_t topic_len = static_cast<uint8_t>(topic.length());
        std::memcpy(buf + offset, &topic_len, sizeof(uint8_t));
        offset += sizeof(uint8_t);
        std::memcpy(buf + offset, topic.data(), topic_len);

        return true;
    }

    static GetCurrentRequestMsg Deserialize(const void* data, size_t data_size)
    {
        GetCurrentRequestMsg msg;
        const char* buf = static_cast<const char*>(data);
        size_t offset = 0;

        // Read topic length
        uint8_t topic_len;
        std::memcpy(&topic_len, buf + offset, sizeof(uint8_t));
        offset += sizeof(uint8_t);

        // Read topic
        msg.topic = std::string(buf + offset, topic_len);

        return msg;
    }
};

// GET_CURRENT response format: [has_message (1 byte)][message if has_message==1]
using GetCurrentResponseMsg = GetNextResponseMsg;

// GET_RATE request format: [topic_length (1 byte)][topic (variable)]
struct GetRateRequestMsg
{
    std::string topic;

    // Get serialized size of this message
    size_t GetSize() const
    {
        return sizeof(uint8_t) + topic.length();
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        size_t required_size = GetSize();
        if (buffer_size < required_size) return false;

        char* buf = static_cast<char*>(buffer);
        size_t offset = 0;

        // Write topic [length (1 byte)][string bytes]
        uint8_t topic_len = static_cast<uint8_t>(topic.length());
        std::memcpy(buf + offset, &topic_len, sizeof(uint8_t));
        offset += sizeof(uint8_t);
        std::memcpy(buf + offset, topic.data(), topic_len);

        return true;
    }

    static GetRateRequestMsg Deserialize(const void* data, size_t data_size)
    {
        GetRateRequestMsg msg;
        const char* buf = static_cast<const char*>(data);
        size_t offset = 0;

        // Read topic length
        uint8_t topic_len;
        std::memcpy(&topic_len, buf + offset, sizeof(uint8_t));
        offset += sizeof(uint8_t);

        // Read topic
        msg.topic = std::string(buf + offset, topic_len);

        return msg;
    }
};

// GET_RATE response format: [rate (8 bytes)]
struct GetRateResponseMsg
{
    double rate;

    static size_t GetSize()
    {
        return sizeof(double);
    }

    bool Serialize(void* buffer, size_t buffer_size) const
    {
        if (buffer_size < GetSize()) return false;
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

// LIST_TOPICS request format: [empty]
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

// LIST_TOPICS response format: [num_topics (4 bytes)][for each: topic_len (4 bytes)][topic (variable)]
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
	// Format: [topic_length (1 byte)][topic (variable)][payload_size (8 bytes)][memory_block_id (1 byte)][payload (variable)]

	// Safety check - header should never be null
	if (!msg.m_Header)
	{
		throw std::runtime_error("Cannot serialize message with null header");
	}

	const MessageHeader &header = *msg.m_Header;
	size_t payload_size = msg.GetPayloadSize();

	// Create message struct
	PublishMsg pub_msg;
	pub_msg.topic = std::string(msg.GetTopic().data());
	pub_msg.payload_size = payload_size;
	pub_msg.memory_block_id = header.payload_info.memory_block_id;
	pub_msg.array_info = msg.GetArrayInfo();
	pub_msg.payload = msg.GetPayload().data;

	// Allocate buffer and serialize
	std::string result;
	result.resize(pub_msg.GetSize());
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
	msg.topic = topic;
	msg.frame_id = frame_id;
	msg.mode = static_cast<uint8_t>(mode);
	msg.timeout = timeout;

	// Allocate buffer and serialize
	std::string result;
	result.resize(msg.GetSize());
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
		req.topic = topic_str;

		std::string request_data;
		request_data.resize(req.GetSize());
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
		std::memcpy(header->topic, resp.message.topic.data(), std::min(resp.message.topic.length(), static_cast<size_t>(TOPIC_MAX_KEY_SIZE - 1)));
		header->topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';
		header->payload_info.total_size = resp.message.payload_size;
		header->payload_info.memory_block_id = resp.message.memory_block_id;
		header->payload_info.offset_in_buffer = 0;

		void* payload = std::malloc(resp.message.payload_size);
		if (resp.message.payload_size > 0 && resp.message.payload)
		{
			std::memcpy(payload, resp.message.payload, resp.message.payload_size);
		}

		Message result(header, payload, 0);
		result.SetArrayInfo(resp.message.array_info);

		DEBUG_PRINT("deserialized message, payload_size: " << resp.message.payload_size);
		return std::optional<Message>(std::move(result));
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
        return m_LocalBroker->Subscribe(topic, preferred_next_frame_id, mode).GetNextMessage(timeout_in_seconds, wait_type, error_check);
	}
	else
	{
		std::string machine = GetMachineFromTopic(topic_str);
		DEBUG_PRINT("remote machine: " << machine);
		Client& client = GetClientForMachine(machine);

		// Client-side timeout handling: poll with 0.1-second chunks
		// Server caps timeout at 0.1 second to prevent worker thread blocking
		const double CHUNK_TIMEOUT = 0.1;
		Timer timer;
		int mode_int = (mode == MessageSubscriptionMode::NewestOnly) ? 0 : 1;

		while (timer.GetTime() < timeout_in_seconds)
		{
			double elapsed = timer.GetTime();
			double remaining = timeout_in_seconds - elapsed;
			double current_timeout = std::min(remaining, CHUNK_TIMEOUT);

			// Serialize request with current chunk timeout
			std::string request = SerializeGetNextRequest(topic_str, preferred_next_frame_id,
			                                               mode_int, current_timeout);

			// Send GET_NEXT request
			DEBUG_PRINT("sending GET_NEXT request with timeout: " << current_timeout << " (elapsed: " << elapsed << ")");
			std::string response = client.MakeRequest("GET_NEXT", request);
			DEBUG_PRINT("response received, size: " << response.size());

			// Parse response
			GetNextResponseMsg resp = GetNextResponseMsg::Deserialize(response.data(), response.size());

			if (resp.has_message)
			{
				DEBUG_PRINT("message received after " << timer.GetTime() << " seconds");

				// Convert PublishMsg to Message
				MessageHeader* header = new MessageHeader();
				std::memset(header, 0, sizeof(MessageHeader));
				std::memcpy(header->topic, resp.message.topic.data(), std::min(resp.message.topic.length(), static_cast<size_t>(TOPIC_MAX_KEY_SIZE - 1)));
				header->topic[TOPIC_MAX_KEY_SIZE - 1] = '\0';
				header->payload_info.total_size = resp.message.payload_size;
				header->payload_info.memory_block_id = resp.message.memory_block_id;
				header->payload_info.offset_in_buffer = 0;

				void* payload = std::malloc(resp.message.payload_size);
				if (resp.message.payload_size > 0 && resp.message.payload)
				{
					std::memcpy(payload, resp.message.payload, resp.message.payload_size);
				}

				Message result(header, payload, 0);
				result.SetArrayInfo(resp.message.array_info);

				DEBUG_PRINT("deserialized message, payload_size: " << resp.message.payload_size);
				return std::optional<Message>(std::move(result));
			}

			DEBUG_PRINT("no message after " << timer.GetTime() << " seconds");

			// Check error callback if provided
			if (error_check)
			{
				error_check();
			}
		}

		DEBUG_PRINT("timeout expired after " << timer.GetTime() << " seconds, no message");
		return std::nullopt;
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
		req.topic = topic_str;

		std::string request_data;
		request_data.resize(req.GetSize());
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

	// Deserialize using the struct (zero-copy payload)
	PublishMsg msg = PublishMsg::Deserialize(request_data.data(), request_data.size());

	DEBUG_PRINT("Message topic: " << msg.topic);
	DEBUG_PRINT("Message payload_size: " << msg.payload_size);
	DEBUG_PRINT("m_Broker ptr: " << m_Broker.get());
	DEBUG_PRINT("Memory block Id: " << (int)msg.memory_block_id);

	Message prepared_msg = m_Broker->PrepareMessage(msg.topic, msg.payload_size, msg.memory_block_id);

	DEBUG_PRINT("Prepared message.");

	// Copy array info
	prepared_msg.SetArrayInfo(msg.array_info);
	DEBUG_PRINT("Copied array info.");

	std::memcpy(prepared_msg.GetPayload().data, msg.payload, msg.payload_size);

	DEBUG_PRINT("Copied payload.");

	// Publish to local broker
	m_Broker->PublishMessage(prepared_msg, true);

	DEBUG_PRINT("PublishMessage completed successfully");
	return "OK";
}

std::string RemoteBrokerServer::HandleGetNext(const std::string& request_data)
{
	DEBUG_PRINT("called, request_size: " << request_data.size());

	// Parse request using struct directly
	GetNextRequestMsg req = GetNextRequestMsg::Deserialize(request_data.data(), request_data.size());
	std::string topic(req.topic);
	MessageSubscriptionMode mode = (req.mode == 0) ? MessageSubscriptionMode::NewestOnly : MessageSubscriptionMode::Sequential;

	DEBUG_PRINT("calling GetNextMessage for topic: " << topic);
	// Cap server-side timeout at 1 second to prevent worker thread blocking
	const double MAX_SERVER_TIMEOUT = 1.0;
	double server_timeout = std::min(req.timeout, MAX_SERVER_TIMEOUT);
	auto msg_opt = m_Broker->Subscribe(topic, req.frame_id, mode).GetNextMessage(server_timeout);
	DEBUG_PRINT("GetNextMessage returned has_value: " << msg_opt.has_value());

	// Serialize response using struct
	GetNextResponseMsg resp;
	resp.has_message = msg_opt.has_value() ? 1 : 0;

	if (msg_opt.has_value())
	{
		Message& inner_msg = msg_opt.value();
		resp.message.topic = std::string(inner_msg.GetTopic().data());
		resp.message.payload_size = inner_msg.GetPayloadSize();
		resp.message.memory_block_id = inner_msg.m_Header ? inner_msg.m_Header->payload_info.memory_block_id : 0;
		resp.message.array_info = inner_msg.GetArrayInfo();
		resp.message.payload = inner_msg.GetPayload().data;
	}

	std::string result;
	result.resize(resp.GetSize());
	if (!resp.Serialize(&result[0], result.size()))
		throw std::runtime_error("Something went wrong during serialization or the message.");

	DEBUG_PRINT("serialized response size: " << result.size());
	return result;
}

std::string RemoteBrokerServer::HandleGetCurrent(const std::string& request_data)
{
	DEBUG_PRINT("request_size: " << request_data.size());

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
		resp.message.topic = std::string(inner_msg.GetTopic().data());
		resp.message.payload_size = inner_msg.GetPayloadSize();
		resp.message.memory_block_id = inner_msg.m_Header ? inner_msg.m_Header->payload_info.memory_block_id : 0;
		resp.message.array_info = inner_msg.GetArrayInfo();
		resp.message.payload = inner_msg.GetPayload().data;
	}

	std::string result;
	result.resize(resp.GetSize());
	if (!resp.Serialize(&result[0], result.size()))
		throw std::runtime_error("Something went wrong during serialization of the response.");

	DEBUG_PRINT("serialized size: " << result.size());
	return result;
}

std::string RemoteBrokerServer::HandleGetRate(const std::string& request_data)
{
	DEBUG_PRINT("request_size: " << request_data.size());

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
	result.resize(resp.GetSize());

	if (!resp.Serialize(&result[0], result.size()))
		throw std::runtime_error("Something went wrong during serialization of the response.");

	return result;
}

std::string RemoteBrokerServer::HandleListTopics(const std::string& request_data)
{
	(void)request_data; // Unused
	DEBUG_PRINT("called");

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
