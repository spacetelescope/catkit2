#ifndef MESSAGE_BROKER_H
#define MESSAGE_BROKER_H

#include "HashMap.h"
#include "Event.h"
#include "FreeListAllocator.h"
#include "PoolAllocator.h"
#include "SharedMemory.h"
#include "LocalMemory.h"
#include "CudaSharedMemory.h"
#include "UuidGenerator.h"
#include "RingBuffer.h"

#include <memory>
#include <map>
#include <array>

const std::array<std::uint8_t, 4> MESSAGE_BROKER_VERSION = {0, 1, 0, 0};

const size_t VERSION_SIZE = 8;
const size_t TOPIC_HASH_MAP_SIZE = 16384;
const size_t TOPIC_MAX_KEY_SIZE = 128;
const size_t TOPIC_MAX_NUM_MESSAGES = 32;
const size_t HOST_NAME_SIZE = 64;
const size_t METADATA_MAX_STRLEN = 16;
const size_t MAX_NUM_MESSAGES = 65536;
const size_t MAX_NUM_DIMENSIONS = 4;
const size_t MAX_NUM_METADATA_ENTRIES = 16;
const size_t MAX_SHARED_MEMORY_ID_SIZE = 64;
const size_t MAX_NUM_BLOCKS = 8192;
const size_t MEMORY_ALIGNMENT = 32;
const size_t NUM_EVENTS_IN_BUFFER = 64;

const std::uint64_t INVALID_FRAME_ID = 0xFFFFFFFFFFFFFFFF;

union MetadataEntry
{
	std::uint64_t integer;
	double floating_point;
	char string[METADATA_MAX_STRLEN];
};

struct ArrayInfo
{
	char data_type;
	char byte_order;
	std::uint8_t num_dimensions;
	std::uint32_t shape[MAX_NUM_DIMENSIONS];
	std::uint32_t strides[MAX_NUM_DIMENSIONS];
};

struct PayloadInfo
{
	std::uint8_t memory_block_id;
	std::uint64_t offset_in_buffer;
	std::uint64_t total_size;

	ArrayInfo array_info;
};

struct MessageHeader
{
	char topic[TOPIC_MAX_KEY_SIZE];

	Uuid payload_id;
	std::uint64_t frame_id;

	Uuid trace_id;

	char producer_hostname[HOST_NAME_SIZE];
	std::uint32_t producer_pid;
	std::uint64_t producer_timestamp;

	PayloadInfo payload_info;

	MetadataEntry metadata_entries[MAX_NUM_METADATA_ENTRIES];

	std::uint16_t partial_frame_id;
	std::uint64_t start_byte;
	std::uint64_t end_byte;
};

struct TopicHeader
{
	std::atomic_uint64_t next_frame_id;
	std::atomic_uint64_t first_frame_id;
	std::atomic_uint64_t last_frame_id;

	std::uint64_t message_headers[TOPIC_MAX_NUM_MESSAGES];

	std::array<char, Event::GetSharedStateSize()> event;

	char metadata_keys[METADATA_MAX_STRLEN][MAX_NUM_METADATA_ENTRIES];
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
	std::uint64_t GetFrameId() const;
	std::uint16_t GetPartialFrameId() const;

	const Uuid &GetTraceId() const;

	std::string_view GetProducerHostnname() const;
	std::uint32_t GetProducerPid() const;
	std::uint64_t GetProducerTimestamp() const;

	const PayloadInfo &GetPayloadInfo() const;

	const ArrayInfo &GetArrayInfo() const;
	void SetArrayInfo(const ArrayInfo &array_info);

	void *GetPayload() const;
	std::size_t GetPayloadSize() const;

	const MetadataEntry &GetMetadataEntry(std::uint8_t metadata_id) const;
	void SetMetadataEntry(std::uint8_t metadata_id, std::uint64_t value);
	void SetMetadataEntry(std::uint8_t metadata_id, double value);
	void SetMetadataEntry(std::uint8_t metadata_id, std::string_view value);

	const std::uint64_t GetStartByte() const;
	void SetStartByte(std::uint64_t start_byte);

	const std::uint64_t GetEndByte() const;
	void SetEndByte(std::uint64_t end_byte);

private:
	MessageHeader *m_Header;
	void *m_Payload;

	bool m_HasBeenPublished;
};

class MessageBroker : public Shareable
{
	friend class Message;

private:
	MessageBroker(
		MessageBrokerHeader *header,
		std::unique_ptr<HashMap> topic_headers,
		std::unique_ptr<PoolAllocator> message_header_allocator,
		std::unique_ptr<RingBuffer> event_allocator,
		std::vector<std::shared_ptr<FreeListAllocator>> allocators,
		std::vector<std::shared_ptr<Memory>> memory_blocks
	);

public:
	static std::unique_ptr<MessageBroker> Create(StructStream &stream, std::vector<std::shared_ptr<Memory>> memory_blocks); // TODO: Add parameters.
	static std::unique_ptr<MessageBroker> Open(StructStream &stream);

	static std::size_t CalculateBufferSize(); // TODO: Add parameters.

	Message PrepareMessage(std::string_view topic, size_t payload_size, uint8_t memory_block_id = 0);
	Message PrepareMessage(std::string_view topic, Uuid trace_id, size_t payload_size, uint8_t memory_block_id = 0);

	void PublishMessage(Message &message, bool is_final = true);

	Message GetNextMessage(std::string_view topic, double timeout_in_seconds);
	Message GetMessage(std::string_view topic, size_t frame_id);

	ShareableType GetType() const override;

private:
	std::shared_ptr<FreeListAllocator> GetAllocator(uint8_t memory_block_id);
	std::shared_ptr<Memory> GetMemory(uint8_t memory_block_id);

	std::shared_ptr<Event> GetEvent(std::string_view topic);

	TopicHeader *GetTopicHeader(std::string_view topic);

	MessageBrokerHeader *m_Header;

	std::unique_ptr<HashMap> m_TopicHeaders;
	std::map<std::string_view, std::shared_ptr<Event>> m_Events;

	std::unique_ptr<RingBuffer> m_EventAllocator;

	std::unique_ptr<PoolAllocator> m_MessageHeaderAllocator;
	MessageHeader *m_MessageHeaders;

	std::vector<std::shared_ptr<FreeListAllocator>> m_Allocators;
	std::vector<std::shared_ptr<Memory>> m_MemoryBlocks;

	UuidGenerator m_UuidGenerator;
};

#endif // MESSAGE_BROKER_H
