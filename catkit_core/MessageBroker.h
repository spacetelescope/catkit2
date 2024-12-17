#ifndef MESSAGE_BROKER_H
#define MESSAGE_BROKER_H

#include "HashMap.h"
#include "Synchronization.h"
#include "FreeListAllocator.h"
#include "PoolAllocator.h"
#include "SharedMemory.h"
#include "CudaSharedMemory.h"
#include "UuidGenerator.h"

const char * const MESSAGE_BROKER_VERSION = "0.1";

const size_t VERSION_SIZE = 8;
const size_t TOPIC_HASH_MAP_SIZE = 16384;
const size_t TOPIC_MAX_KEY_SIZE = 128;
const size_t TOPIC_MAX_NUM_MESSAGES = 15;
const size_t HOST_NAME_SIZE = 64;
const size_t METADATA_MAX_STRLEN = 15;
const size_t UUID_SIZE = 16;
const size_t MAX_NUM_DIMENSIONS = 4;
const size_t MAX_NUM_METADATA_ENTRIES = 16;
const size_t MAX_SHARED_MEMORY_ID_SIZE = 64;
const size_t MAX_NUM_GPUS = 8;

struct MetadataEntry
{
// Avoid post-padding of this anonymous union.
#pragma pack(push,1)
    union
    {
        std::uint64_t integer;
        double floating_point;
        char string[METADATA_MAX_STRLEN];
    };
#pragma pack(pop)

	std::uint8_t metadata_id;
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

	char payload_id[UUID_SIZE];
	std::uint64_t frame_id;

	char trace_id[UUID_SIZE];

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
	std::atomic_uint64_t latest_frame_id;
	std::uint64_t message_offsets[TOPIC_MAX_NUM_MESSAGES];
	char message_ids[UUID_SIZE][TOPIC_MAX_NUM_MESSAGES];

	SynchronizationSharedData synchronization;
};

struct MessageBrokerHeader
{
	char version[VERSION_SIZE];
	char creator_hostname[HOST_NAME_SIZE];
	std::uint64_t time_of_last_activity;

	char buffer_shared_memory_id[MAX_SHARED_MEMORY_ID_SIZE];
	CudaIpcHandle cuda_ipc_handles[MAX_NUM_GPUS];
};

struct Message
{
	MessageHeader *header;
	void *payload;
};

class MessageBroker
{
public:
	MessageBroker(void *metadata_buffer);

	void Initialize();

	void *ReservePayload(size_t payload_size, int8_t device_id = -1);

	void Publish(const std::string &topic, const Message &message);
	void PublishPartial(const std::string &topic, const Message &message);

	Message GetNextMessage(const std::string &topic, double timeout_in_seconds);
	Message GetMessage(const std::string &topic, size_t frame_id);

private:
	MessageBrokerHeader &m_Header;

	HashMap<TopicHeader, TOPIC_HASH_MAP_SIZE, TOPIC_MAX_KEY_SIZE> m_TopicHeaders;
	PoolAllocator m_MessageHeaderAllocator;

	FreeListAllocator m_CpuPayloadAllocator;
	std::shared_ptr<SharedMemory> m_CpuPayloadMemory;

	FreeListAllocator m_GpuPayloadAllocator[MAX_NUM_GPUS];
	std::shared_ptr<CudaSharedMemory> m_GpuPayloadMemory[MAX_NUM_GPUS];

	UuidGenerator m_UuidGenerator;
};

#endif // MESSAGE_BROKER_H
