#ifndef MESSAGE_BROKER_H
#define MESSAGE_BROKER_H

#include "Uuid.h"
#include "HybridPoolAllocator.h"
#include "Event.h"

#include <optional>
#include <array>
#include <cstdint>
#include <cstddef>
#include <memory>
#include <string>

const size_t HOST_NAME_SIZE = 64;
const size_t TOPIC_MAX_KEY_SIZE = 127;
const size_t METADATA_MAX_STRLEN = 8;
const size_t METADATA_MAX_KEYLEN = 7;
const size_t MAX_NUM_DIMENSIONS = 4;
const size_t MAX_NUM_METADATA_ENTRIES = 12;
const size_t MAX_SHARED_MEMORY_ID_SIZE = 64;
const size_t MAX_NUM_BLOCKS = 8192;
const size_t MEMORY_ALIGNMENT = 32;
const size_t MIN_SIZE_POOL = 1024;
const size_t NUM_EVENTS_IN_BUFFER = 64;

const std::uint64_t INVALID_FRAME_ID = 0xFFFFFFFFFFFFFFFF;

enum class MetadataType : std::uint8_t
{
	Integer,
	Float,
	String
};

union MetadataValue
{
	std::int64_t integer;
	double floating_point;
	std::array<char, METADATA_MAX_STRLEN> string;
};

struct MetadataEntry
{
	std::array<char, METADATA_MAX_KEYLEN> key;
	MetadataType type;
	MetadataValue value;
};

struct ArrayInfo
{
	char data_type;
	char byte_order;
	std::uint8_t item_size;
	std::uint8_t ndim;
	std::uint32_t shape[MAX_NUM_DIMENSIONS];
	std::uint32_t strides[MAX_NUM_DIMENSIONS];

	std::size_t GetNumItems() const;
	std::size_t GetNumBytes() const;
};

struct PayloadInfo
{
	std::uint8_t memory_block_id;
	HybridPoolAllocator::Handle block_handle;
	std::uint64_t offset_in_buffer;
	std::uint64_t total_size;

	ArrayInfo array_info;
};

struct MessageHeader
{
	char topic[TOPIC_MAX_KEY_SIZE];

	Uuid payload_id;
	Uuid trace_id;

	char producer_hostname[HOST_NAME_SIZE];
	std::uint32_t producer_pid;
	std::uint64_t producer_timestamp;

	PayloadInfo payload_info;
	std::uint64_t start_byte;
	std::uint64_t end_byte;

	std::uint16_t partial_frame_id;

	std::uint8_t num_metadata_entries;
	MetadataEntry metadata_entries[MAX_NUM_METADATA_ENTRIES];
};

class MessageBroker;

class Message
{
	friend class MessageBroker;

private:
	Message(MessageHeader *header, void *payload, bool has_been_published = false);

public:
	std::string_view GetTopic() const;

	const Uuid &GetPayloadId() const;
	std::uint16_t GetPartialFrameId() const;

	const Uuid &GetTraceId() const;

	std::string_view GetProducerHostname() const;
	std::uint32_t GetProducerPid() const;
	std::uint64_t GetProducerTimestamp() const;

	const PayloadInfo &GetPayloadInfo() const;

	const ArrayInfo &GetArrayInfo() const;
	void SetArrayInfo(const ArrayInfo &array_info);

	void *GetPayload() const;
	std::size_t GetPayloadSize() const;

	MetadataEntry *GetMetadataEntry(std::string_view key, bool create_if_not_exists = false);
	void SetMetadataEntry(std::string_view key, std::int64_t value);
	void SetMetadataEntry(std::string_view key, double value);
	void SetMetadataEntry(std::string_view key, std::string_view value);

	const std::uint64_t GetStartByte() const;
	void SetStartByte(std::uint64_t start_byte);

	const std::uint64_t GetEndByte() const;
	void SetEndByte(std::uint64_t end_byte);

private:
	MessageHeader *m_Header;
	void *m_Payload;

	bool m_HasBeenPublished;
};

enum class MessageSubscriptionMode
{
	// Only the latest messages are processed, skipping older ones
	NewestOnly,
	// Messages are processed in order without skipping
	Sequential,
};

class MessageSubscription
{
	friend class MessageBroker;

public:
	Message GetNextMessage(double timeout_in_seconds = -1, EventWaitMethod wait_type = EventWaitMethod::Default, void (*error_check)() = nullptr);
	std::optional<Message> TryGetNextMessage();

	std::uint64_t GetNextMessageId();

private:
	MessageSubscription(std::shared_ptr<MessageBroker>, std::string_view topic, std::uint64_t starting_frame_id, MessageSubscriptionMode mode);

	std::shared_ptr<MessageBroker> m_MessageBroker;

    std::string m_Topic;
	std::uint64_t m_NextFrameIdToRead;
	MessageSubscriptionMode m_SubscriptionMode;
};

class MessageBroker : public std::enable_shared_from_this<MessageBroker>
{
public:
    // Prepare a message for publishing.
	Message PrepareMessage(std::string_view topic, size_t payload_size, uint8_t memory_block_id = 0);

	// Prepare a message for publishing with a trace ID.
	virtual Message PrepareMessage(std::string_view topic, size_t payload_size, Uuid trace_id, uint8_t memory_block_id = 0) = 0;

	// Publish a message.
	virtual void PublishMessage(Message &message, bool is_final = true) = 0;

	// Convenience function for publishing data.
	void PublishData(std::string_view topic, const void *data, size_t data_size, uint8_t memory_block_id = 0);

	// Convenience function for publishing data with a trace ID.
	void PublishData(std::string_view topic, const void *data, size_t data_size, Uuid trace_id, uint8_t memory_block_id = 0);

	// Get the newest message for a topic.
	virtual std::optional<Message> GetCurrentMessage(std::string_view topic) = 0;

    // Get the next message for a topic.
    virtual Message GetNextMessage(std::string_view topic, std::uint64_t frame_id, MessageSubscriptionMode mode, double timeout_in_sec, EventWaitMethod wait_method, void (*error_check)() = nullptr) = 0;

    // Try and get the next message for a topic.
    virtual std::optional<Message> TryGetNextMessage(std::string_view topic, std::uint64_t frame_id, MessageSubscriptionMode mode) = 0;

    // Subscribe to a topic for receiving messages.
	MessageSubscription Subscribe(std::string_view topic, MessageSubscriptionMode mode = MessageSubscriptionMode::NewestOnly);

	// Subscribe to a topic for receiving messages with a starting frame ID.
	MessageSubscription Subscribe(std::string_view topic, size_t starting_frame_id, MessageSubscriptionMode mode = MessageSubscriptionMode::NewestOnly);

    virtual double GetMessageRate(std::string_view topic) = 0;

	// Get the message topics for all messages in this broker.
	virtual std::vector<std::string> GetAllMessageTopics() = 0;
};

#endif // MESSAGE_BROKER_H
