#ifndef MESSAGE_BROKER_H
#define MESSAGE_BROKER_H

#include "HashMap.h"
#include "Event.h"
#include "HybridPoolAllocator.h"
#include "PoolAllocator.h"
#include "SharedMemory.h"
#include "LocalMemory.h"
#include "CudaSharedMemory.h"
#include "Uuid.h"
#include "RingBuffer.h"

#include <memory>
#include <array>
#include <unordered_map>

const std::array<std::uint8_t, 4> MESSAGE_BROKER_VERSION = {0, 1, 0, 0};

const size_t VERSION_SIZE = 8;
const size_t TOPIC_HASH_MAP_SIZE = 16384;
const size_t TOPIC_MAX_KEY_SIZE = 127;
const size_t TOPIC_MAX_NUM_MESSAGES = 32;
const size_t HOST_NAME_SIZE = 64;
const size_t METADATA_MAX_STRLEN = 8;
const size_t METADATA_MAX_KEYLEN = 7;
const size_t MAX_NUM_MESSAGES = 65536;
const size_t MAX_NUM_DIMENSIONS = 4;
const size_t MAX_NUM_METADATA_ENTRIES = 16;
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

struct TopicHeader
{
	std::atomic_uint64_t next_frame_id;
	std::atomic_uint64_t first_frame_id;
	std::atomic_uint64_t last_frame_id;

	double frame_rate;

	std::array<std::uint64_t, TOPIC_MAX_NUM_MESSAGES> message_headers;
};

struct MessageBrokerHeader
{
	char creator_hostname[HOST_NAME_SIZE];
	std::uint64_t time_of_creation;
	int creator_pid;

	std::size_t num_memory_blocks;

	std::uint64_t time_of_last_activity;

	MessageHeader message_headers[MAX_NUM_MESSAGES];
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

class MessageSubscription
{
};

class MessageBroker : public Shareable
{
	friend class Message;

private:
	MessageBroker(
		MessageBrokerHeader *header,
		std::unique_ptr<HashMap> topic_headers,
		std::unique_ptr<PoolAllocator> message_header_allocator,
		std::unique_ptr<Event> event,
		std::vector<std::shared_ptr<HybridPoolAllocator>> allocators,
		std::vector<std::shared_ptr<Memory>> memory_blocks
	);

public:
	static std::unique_ptr<MessageBroker> Create(StructStream &stream, std::vector<std::shared_ptr<Memory>> memory_blocks);
	static std::unique_ptr<MessageBroker> Open(StructStream &stream);

	static std::size_t CalculateBufferSize(); // TODO: Add parameters.

	Message PrepareMessage(std::string_view topic, size_t payload_size, uint8_t memory_block_id = 0);
	Message PrepareMessage(std::string_view topic, Uuid trace_id, size_t payload_size, uint8_t memory_block_id = 0);

	void PublishMessage(Message &message, bool is_final = true);

	Message GetMessage(std::string_view topic, size_t frame_id, double timeout_in_seconds = -1, EventWaitMethod wait_type = EventWaitMethod::Default, void (*error_check)() = nullptr);
	Message GetNewestMessage(std::string_view topic);

	bool IsMessageAvailable(std::string_view topic, size_t frame_id);
	bool WillMessageBeAvailable(std::string_view topic, size_t frame_id);

	size_t GetNewestMessageId(std::string_view topic);
	size_t GetOldestMessageId(std::string_view topic);

	double GetMessageRate(std::string_view topic);

	std::vector<std::string> GetAllMessageTopics();

	MessageSubscription Subscribe(std::string_view topic);

	ShareableType GetType() const override;

private:
	Message GetMessage(TopicHeader *topic_header, size_t frame_id);

	std::shared_ptr<HybridPoolAllocator> GetAllocator(uint8_t memory_block_id);
	std::shared_ptr<Memory> GetMemory(uint8_t memory_block_id);

	TopicHeader *GetTopicHeader(std::string_view topic);

	MessageBrokerHeader *m_Header;

	std::unique_ptr<HashMap> m_TopicHeaders;

	std::shared_ptr<Event> m_Event;

	std::unique_ptr<PoolAllocator> m_MessageHeaderAllocator;
	MessageHeader *m_MessageHeaders;

	std::vector<std::shared_ptr<HybridPoolAllocator>> m_Allocators;
	std::vector<std::shared_ptr<Memory>> m_MemoryBlocks;
};

#endif // MESSAGE_BROKER_H
