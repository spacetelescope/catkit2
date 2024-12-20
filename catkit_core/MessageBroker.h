#ifndef MESSAGE_BROKER_H
#define MESSAGE_BROKER_H

#include "HashMap.h"
#include "Synchronization.h"
#include "FreeListAllocator.h"
#include "PoolAllocator.h"
#include "SharedMemory.h"
#include "CudaSharedMemory.h"
#include "UuidGenerator.h"

#include <memory>

const char * const MESSAGE_BROKER_VERSION = "0.1";

const size_t VERSION_SIZE = 8;
const size_t TOPIC_HASH_MAP_SIZE = 16384;
const size_t TOPIC_MAX_KEY_SIZE = 128;
const size_t TOPIC_MAX_NUM_MESSAGES = 15;
const size_t HOST_NAME_SIZE = 64;
const size_t METADATA_MAX_STRLEN = 16;
const size_t MAX_NUM_DIMENSIONS = 4;
const size_t MAX_NUM_METADATA_ENTRIES = 16;
const size_t MAX_SHARED_MEMORY_ID_SIZE = 64;
const size_t MAX_NUM_GPUS = 8;

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
	std::int8_t device_id;
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
	std::uint64_t message_offsets[TOPIC_MAX_NUM_MESSAGES];

	SynchronizationSharedData synchronization;

	char metadata_keys[METADATA_MAX_STRLEN][MAX_NUM_METADATA_ENTRIES];

	TopicHeader() = default;
	TopicHeader(const TopicHeader &header);

	TopicHeader &operator=(const TopicHeader &header);

private:
	void CopyFrom(const TopicHeader &header);
};

struct MessageBrokerHeader
{
	char version[VERSION_SIZE];
	char creator_hostname[HOST_NAME_SIZE];
	std::uint64_t time_of_last_activity;

	char buffer_shared_memory_id[MAX_SHARED_MEMORY_ID_SIZE];
	CudaIpcHandle cuda_ipc_handles[MAX_NUM_GPUS];
};

class MessageBroker;

class Message
{
	friend class MessageBroker;

private:
	Message();

public:
	~Message();

	const char *GetTopic() const;

	const Uuid &GetPayloadId() const;
	const std::uint64_t GetFrameId() const;

	const Uuid &GetTraceId() const;

	const char *GetProducerHostnname() const;
	const std::uint32_t GetProducerPid() const;
	const std::uint64_t GetProducerTimestamp() const;

	const PayloadInfo &GetPayloadInfo() const;

	const ArrayInfo &GetArrayInfo() const;
	void SetArrayInfo(const ArrayInfo &array_info);

	void *GetPayload() const;
	size_t GetPayloadSize() const;

	const MetadataEntry &GetMetadataEntry(std::uint8_t metadata_id) const;
	void SetMetadataEntry(std::uint8_t metadata_id, std::uint64_t value);
	void SetMetadataEntry(std::uint8_t metadata_id, double value);
	void SetMetadataEntry(std::uint8_t metadata_id, const char *value);

	const std::uint16_t GetPartialFrameId() const;

	const std::uint64_t GetStartByte() const;
	void SetStartByte(const std::uint64_t &start_byte);

	const std::uint64_t GetEndByte() const;
	void SetEndByte(const std::uint64_t &end_byte);

private:
	MessageHeader *m_Header;
	void *m_Payload;

	bool m_HasBeenPublished;

	std::shared_ptr<MessageBroker> m_MessageBroker;
};

class MessageBroker : std::enable_shared_from_this<MessageBroker>
{
	friend class Message;

private:
	MessageBroker(); // TODO: Add parameters.

public:
	std::unique_ptr<MessageBroker> Create(); // TODO: Add parameters.
	std::unique_ptr<MessageBroker> Open(void *metadata_buffer);

	Message PrepareMessage(const std::string &topic, size_t payload_size, int8_t device_id = -1);
	Message PrepareMessage(const std::string &topic, Uuid trace_id, size_t payload_size, int8_t device_id = -1);

	void PublishMessage(Message &message, bool is_final = true);

	Message GetNextMessage(const std::string &topic, double timeout_in_seconds);
	Message GetMessage(const std::string &topic, size_t frame_id);

private:
	FreeListAllocator *GetAllocator(int8_t device_id);
	Synchronization *GetSynchronization(const std::string &topic);

	MessageBrokerHeader &m_Header;

	HashMap<TopicHeader, TOPIC_HASH_MAP_SIZE, TOPIC_MAX_KEY_SIZE> m_TopicHeaders;
	PoolAllocator m_MessageHeaderAllocator;

	MessageHeader *m_MessageHeaders;

	FreeListAllocator m_CpuPayloadAllocator;
	std::shared_ptr<SharedMemory> m_CpuPayloadMemory;

	FreeListAllocator m_GpuPayloadAllocator[MAX_NUM_GPUS];
	std::shared_ptr<CudaSharedMemory> m_GpuPayloadMemory[MAX_NUM_GPUS];

	UuidGenerator m_UuidGenerator;
};

#endif // MESSAGE_BROKER_H
