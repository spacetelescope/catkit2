#ifndef LOCAL_MESSAGE_BROKER_H
#define LOCAL_MESSAGE_BROKER_H

#include "HashMap.h"
#include "Event.h"
#include "HybridPoolAllocator.h"
#include "PoolAllocator.h"
#include "SharedMemory.h"
#include "LocalMemory.h"
#include "CudaSharedMemory.h"
#include "Uuid.h"
#include "ArrayView.h"
#include "MessageBroker.h"

#include <memory>
#include <array>
#include <optional>

const std::array<std::uint8_t, 4> MESSAGE_BROKER_VERSION = {0, 1, 0, 0};

const size_t TOPIC_HASH_MAP_SIZE = 16384;
const size_t TOPIC_MAX_NUM_MESSAGES = 32;
const size_t MAX_NUM_MESSAGES = 65536;
const size_t MAX_NUM_BLOCKS = 8192;
const size_t MEMORY_ALIGNMENT = 32;
const size_t MIN_SIZE_POOL = 1024;
const size_t EVENT_POOL_SIZE = 128;

struct TopicHeader
{
	std::atomic_uint64_t next_frame_id;
	std::atomic_uint64_t first_frame_id;
	std::atomic_uint64_t last_frame_id;

	double frame_rate;

	std::array<std::uint64_t, TOPIC_MAX_NUM_MESSAGES> message_headers;

	// Pre-computed event index for this topic (hash of topic name % EVENT_POOL_SIZE)
	std::uint32_t event_index;

	bool IsMessageAvailable(std::size_t frame_id);
	bool WillMessageBeAvailable(std::size_t frame_id);
	std::size_t GetOldestMessageId();
	std::size_t GetNewestMessageId();

	double GetMessageRate();
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

class LocalMessageBroker : public Shareable, public MessageBroker
{
	friend class MessageSubscription;

private:
	LocalMessageBroker(
		MessageBrokerHeader *header,
		std::shared_ptr<HashMap> topic_headers,
		std::shared_ptr<PoolAllocator> message_header_allocator,
		std::array<std::shared_ptr<Event>, EVENT_POOL_SIZE> event_pool,
		std::vector<std::shared_ptr<HybridPoolAllocator>> allocators,
		std::vector<std::shared_ptr<Memory>> memory_blocks,
		std::shared_ptr<Memory> header_memory
	);

public:
	static std::shared_ptr<LocalMessageBroker> Create(StructStream &stream, std::vector<std::shared_ptr<Memory>> memory_blocks);
	static std::shared_ptr<LocalMessageBroker> Open(StructStream &stream);

	static std::size_t CalculateBufferSize(); // TODO: Add parameters.

	// Prepare a message for publishing with a trace ID.
	virtual Message PrepareMessageImpl(std::string_view topic, size_t payload_size, Uuid trace_id, uint8_t memory_block_id = 0) override;

	// Publish a message.
	virtual Message PublishMessage(Message message, bool is_final = true) override;

	// Get the newest message for a topic.
	virtual std::optional<Message> GetCurrentMessage(std::string_view topic) override;

	// Get the message rate for a topic.
	virtual double GetMessageRate(std::string_view topic) override;

	// Get the message topics for all messages in this broker.
	virtual std::vector<std::string> GetAllMessageTopics() override;

	ShareableType GetType() const override;

	virtual void PrintDebugInfo() const override;

protected:
	// Get the next message for a topic.
	virtual std::optional<Message> GetNextMessage(std::string_view topic, size_t preferred_next_frame_id, MessageSubscriptionMode mode = MessageSubscriptionMode::NewestOnly, double timeout_in_seconds = -1, EventWaitMethod wait_type = EventWaitMethod::Default, void (*error_check)() = nullptr) override;

	// Try to get the next message for a topic.
	virtual std::optional<Message> TryGetNextMessage(std::string_view topic, size_t preferred_next_frame_id, MessageSubscriptionMode mode = MessageSubscriptionMode::NewestOnly) override;

private:
	Message FetchMessage(TopicHeader *topic_header, size_t frame_id);
	std::uint64_t GetNextMessageId(TopicHeader *topic_header, size_t preferred_next_frame_id, MessageSubscriptionMode mode);

	std::shared_ptr<HybridPoolAllocator> GetAllocator(uint8_t memory_block_id);
	std::shared_ptr<Memory> GetMemory(uint8_t memory_block_id);

	TopicHeader *GetTopicHeader(std::string_view topic);

	MessageBrokerHeader *m_Header;

	std::shared_ptr<HashMap> m_TopicHeaders;

	std::shared_ptr<Event> m_Event;

	std::shared_ptr<PoolAllocator> m_MessageHeaderAllocator;
	MessageHeader *m_MessageHeaders;

	std::array<std::shared_ptr<Event>, EVENT_POOL_SIZE> m_EventPool;

	std::vector<std::shared_ptr<HybridPoolAllocator>> m_Allocators;
	std::vector<std::shared_ptr<Memory>> m_MemoryBlocks;
};

#endif // LOCAL_MESSAGE_BROKER_H
