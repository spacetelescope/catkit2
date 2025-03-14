#include "MessageBroker.h"

#include "Util.h"
#include "Timing.h"
#include "HostName.h"

#include <algorithm>
#include <cstdint>
#include <iostream>

//#define DEBUG_PRINT(a) std::cout << a << std::endl
#define DEBUG_PRINT(a)

template<typename T>
T fetch_max(std::atomic<T> &atom, T value)
{
	T current = atom.load(std::memory_order_relaxed);

	while (current < value && !atom.compare_exchange_weak(current, value, std::memory_order_acq_rel))
	{
	}

	return current;
}

class SubtopicIterator
{
public:
	SubtopicIterator(std::string_view str, char delimiter, bool is_valid = true)
		: m_String(str), m_Delimiter(delimiter), m_IsValid(is_valid)
	{
	}

	std::string_view operator*() const
	{
		return m_String;
	}

	SubtopicIterator& operator++()
	{
		if (m_String.empty())
		{
			m_IsValid = false;
			return *this;
		}

		size_t pos = m_String.rfind(m_Delimiter);

		if (pos != std::string_view::npos)
		{
			// Remove the last part.
			m_String.remove_suffix(m_String.size() - pos);
		}
		else
		{
			// No more delimiters left, so remove the whole string.
			m_String.remove_suffix(m_String.size());
		}

		return *this;
	}

	bool operator!=(const SubtopicIterator& other) const
	{
		if (!m_IsValid && !other.m_IsValid)
		{
			// If both iterators are invalid, they are equal no matter what.
			return false;
		}

		return m_IsValid == other.m_IsValid ||
			m_String.data() != other.m_String.data() ||
			m_String.size() != other.m_String.size();
	}

	static SubtopicIterator end()
	{
		return SubtopicIterator({}, '\0', true);
	}

private:
	std::string_view m_String;
	char m_Delimiter;
	bool m_IsValid;
};

class SubtopicRange
{
public:
	SubtopicRange(std::string_view str, char delimiter = '/')
		: m_String(str), m_Delimiter(delimiter)
	{
	}

	SubtopicIterator begin() const
	{
		return SubtopicIterator(m_String, m_Delimiter);
	}

	SubtopicIterator end() const
	{
		return SubtopicIterator::end();
	}

private:
	std::string_view m_String;
	char m_Delimiter;
};

MessageBroker::MessageBroker(
	MessageBrokerHeader *header,
	std::unique_ptr<HashMap> topic_headers,
	std::unique_ptr<PoolAllocator> message_header_allocator,
	std::unique_ptr<RingBuffer> event_allocator,
	std::vector<std::shared_ptr<FreeListAllocator>> allocators,
	std::vector<std::shared_ptr<Memory>> memory_blocks
)
	: m_Header(header),
	m_TopicHeaders(std::move(topic_headers)),
	m_MessageHeaderAllocator(std::move(message_header_allocator)),
	m_EventAllocator(std::move(event_allocator)),
	m_Allocators(std::move(allocators)),
	m_MemoryBlocks(memory_blocks),
	m_MessageHeaders(header->message_headers)
{
}

std::unique_ptr<MessageBroker> MessageBroker::Create(StructStream &stream, std::vector<std::shared_ptr<Memory>> memory_blocks)
{
	*stream.Extract<std::array<std::uint8_t, 4>>() = MESSAGE_BROKER_VERSION;

	auto header = stream.Extract<MessageBrokerHeader>();

	GetHostName().copy(header->creator_hostname, HOST_NAME_SIZE);
	header->time_of_creation = GetTimeStamp();
	header->creator_pid = GetProcessId();
	header->num_memory_blocks = memory_blocks.size();

	header->time_of_last_activity = GetTimeStamp();

	auto topic_headers = HashMap::Create(stream, TOPIC_HASH_MAP_SIZE, TOPIC_MAX_KEY_SIZE, sizeof(TopicHeader));

	auto message_header_allocator = PoolAllocator::Create(stream, MAX_NUM_MESSAGES);

	auto event_allocator = RingBuffer::Create(stream, NUM_EVENTS_IN_BUFFER, Event::GetSharedStateSize());

	std::vector<std::shared_ptr<FreeListAllocator>> allocators;

	for (auto memory_block : memory_blocks)
	{
		auto capacity = memory_block->GetCapacity();
		std::shared_ptr<FreeListAllocator> allocator = FreeListAllocator::Create(stream, MAX_NUM_BLOCKS, MEMORY_ALIGNMENT, capacity);

		allocators.push_back(std::move(allocator));

		memory_block->WriteReference(stream);
	}

	return std::unique_ptr<MessageBroker>(new MessageBroker(
		header,
		std::move(topic_headers),
		std::move(message_header_allocator),
		std::move(event_allocator),
		allocators,
		memory_blocks
	));
}

std::unique_ptr<MessageBroker> MessageBroker::Open(StructStream &stream)
{
	CheckVersion(stream, MESSAGE_BROKER_VERSION);

	auto header = stream.Extract<MessageBrokerHeader>();

	auto topic_headers = HashMap::Open(stream);
	auto message_header_allocator = PoolAllocator::Open(stream);
	auto event_allocator = RingBuffer::Open(stream);

	std::vector<std::shared_ptr<FreeListAllocator>> allocators;
	std::vector<std::shared_ptr<Memory>> memory_blocks;

	for (std::size_t i = 0; i < header->num_memory_blocks; ++i)
	{
		auto allocator = FreeListAllocator::Open(stream);
		allocators.push_back(std::move(allocator));

		ShareableType type = *stream.Extract<ShareableType>();
		switch (type)
		{
			case ShareableType::SharedMemory:
				memory_blocks.push_back(SharedMemory::Open(stream));
				break;
			case ShareableType::LocalMemory:
				memory_blocks.push_back(LocalMemory::Open(stream));
				break;
			default:
				throw std::runtime_error("Unknown memory type.");
		}
	}

	return std::unique_ptr<MessageBroker>(new MessageBroker(
		header,
		std::move(topic_headers),
		std::move(message_header_allocator),
		std::move(event_allocator),
		allocators,
		memory_blocks
	));
}

std::size_t MessageBroker::CalculateBufferSize()
{
	return 0;
}

Message MessageBroker::PrepareMessage(std::string_view topic, size_t payload_size, uint8_t memory_block_id)
{
	DEBUG_PRINT("Preparing message.");

	Uuid trace_id;
	m_UuidGenerator.Generate(&trace_id);

	DEBUG_PRINT("Trace id generated.");

	return PrepareMessage(topic, trace_id, payload_size, memory_block_id);
}

Message MessageBroker::PrepareMessage(std::string_view topic, Uuid trace_id, size_t payload_size, uint8_t memory_block_id)
{
	// Allocate a payload.
	auto allocator = GetAllocator(memory_block_id);

	if (allocator == nullptr)
	{
		throw std::runtime_error("Invalid device ID.");
	}

	DEBUG_PRINT("Gotten allocator.");

	auto block_handle = allocator->Allocate(payload_size);

	if (block_handle == FreeListAllocator::INVALID_HANDLE)
	{
		throw std::runtime_error("Could not allocate payload.");
	}

	DEBUG_PRINT("Block allocated.");

	auto offset = allocator->GetOffset(block_handle);

	auto memory = GetMemory(memory_block_id);
	auto payload = memory->GetAddress(offset);

	// Allocate a message header.
	auto message_header_handle = m_MessageHeaderAllocator->Allocate();

	DEBUG_PRINT("Message header allocated: " << message_header_handle);

	if (message_header_handle == PoolAllocator::INVALID_HANDLE)
	{
		// Deallocate allocated memory block.
		// TODO: Do this with RAII.
		allocator->Deallocate(block_handle);

		throw std::runtime_error("Could not allocate message header.");
	}

	// Access the message header.
	auto header = &m_MessageHeaders[message_header_handle];

	DEBUG_PRINT("Message header gotten.");

	// Set the payload information.
	header->payload_info.memory_block_id = memory_block_id;
	DEBUG_PRINT("a");

	header->payload_info.total_size = payload_size;
	header->payload_info.offset_in_buffer = offset;

	m_UuidGenerator.Generate(&header->payload_id);

	DEBUG_PRINT("Payload set");

	// Set the topic.
	std::fill(header->topic, header->topic + sizeof(header->topic), '\0');
	topic.copy(header->topic, TOPIC_MAX_KEY_SIZE - 1);

	DEBUG_PRINT("Header topic set");

	// Set the trace ID.
	header->trace_id = trace_id;

	// Set the producer information.
	std::fill(header->producer_hostname, header->producer_hostname + HOST_NAME_SIZE, '\0');
	GetHostName().copy(header->producer_hostname, HOST_NAME_SIZE - 1);
	header->producer_pid = GetProcessId();

	header->partial_frame_id = 0;
	header->start_byte = 0;
	header->end_byte = payload_size;

	// Set default values.
	header->frame_id = INVALID_FRAME_ID;
	header->producer_timestamp = 0;

	DEBUG_PRINT("Header set");

	return Message(header, payload, false);
}

void MessageBroker::PublishMessage(Message &message, bool is_final)
{
	if (message.m_HasBeenPublished)
	{
		return;
	}

	auto topic = std::string_view(message.m_Header->topic);
	auto topic_header = (TopicHeader *) m_TopicHeaders->Find(topic);

	if (message.m_Header->frame_id == INVALID_FRAME_ID)
	{
		// First partial frame. Assign a new frame ID.
		message.m_Header->frame_id = topic_header->next_frame_id.fetch_add(1, std::memory_order_relaxed);
		message.m_Header->partial_frame_id = 0;

		// If the ring buffer is full, make the oldest frame unavailable.
		if ((topic_header->last_frame_id - topic_header->first_frame_id) >= TOPIC_MAX_NUM_MESSAGES)
		{
			topic_header->first_frame_id++;
		}
	}
	else
	{
		// Not the first partial frame. Use the same frame ID and increment the partial frame ID.
		message.m_Header->partial_frame_id++;
	}

	// Set the timestamp.
	message.m_Header->producer_timestamp = GetTimeStamp();

	// Publish the message to all subtopics.
	for (const auto &subtopic : SubtopicRange(topic))
	{
		auto topic_header = (TopicHeader *) m_TopicHeaders->Find(std::string(subtopic));

		if (!topic_header)
		{
			// TODO: if the topic header doesn't exist, create it.

		}

		auto event = GetEvent(subtopic);

		// Copy over message header reference.
		std::size_t message_header_index = message.m_Header - m_MessageHeaders;
		topic_header->message_headers[message.m_Header->frame_id % TOPIC_MAX_NUM_MESSAGES] = message_header_index;

		{
			// Obtain a lock as we're about to signal the event structure.
			auto lock = EventLockGuard(event);

			// Make the message available.
			fetch_max(topic_header->last_frame_id, message.m_Header->frame_id);

			// Signal the event structure.
			event->Signal();
		}
	}

	if (!is_final)
	{
		// Copy the message header since it's gone after publishing.
		auto message_header_handle = m_MessageHeaderAllocator->Allocate();

		if (message_header_handle == PoolAllocator::INVALID_HANDLE)
		{
			throw std::runtime_error("Could not allocate message header.");
		}

		auto new_message_header = &m_MessageHeaders[message_header_handle];
		*new_message_header = *message.m_Header;
		message.m_Header = new_message_header;
	}

	message.m_HasBeenPublished = is_final;
}

Message MessageBroker::GetNextMessage(std::string_view topic, double timeout_in_seconds)
{
	// TODO: add implementation.
	return Message(nullptr, nullptr, true);
}

Message MessageBroker::GetMessage(std::string_view topic, size_t frame_id)
{
	// TODO: add implementation.
	return Message(nullptr, nullptr, true);
}

ShareableType MessageBroker::GetType() const
{
	return ShareableType::MessageBroker;
}

std::shared_ptr<FreeListAllocator> MessageBroker::GetAllocator(uint8_t memory_block_id)
{
	if (memory_block_id >= m_Allocators.size())
	{
		return nullptr;
	}

	return m_Allocators[memory_block_id];
}

std::shared_ptr<Memory> MessageBroker::GetMemory(uint8_t memory_block_id)
{
	if (memory_block_id >= m_MemoryBlocks.size())
	{
		return nullptr;
	}

	return m_MemoryBlocks[memory_block_id];
}

std::shared_ptr<Event> MessageBroker::GetEvent(std::string_view topic)
{
	// Look up the synchronization structure (not the shared data).
	if (m_Events.find(topic) == m_Events.end())
	{
		auto topic_header = GetTopicHeader(topic);

		if (!topic_header)
			return nullptr;

		// Temporary stream to read in the event.
		auto stream = StructStream(topic_header->event.data());
		m_Events[topic] = Event::Open(stream);
	}

	return m_Events[topic];
}

TopicHeader *MessageBroker::GetTopicHeader(std::string_view topic)
{
	auto topic_header = (TopicHeader *) m_TopicHeaders->Find(topic);

	if (topic_header)
	{
		return topic_header;
	}

	// The topic header doesn't exist, so create it.
	TopicHeader temp_topic_header;

	temp_topic_header.next_frame_id = 0;
	temp_topic_header.first_frame_id = 0;
	temp_topic_header.last_frame_id = 0;

	topic_header = (TopicHeader *) m_TopicHeaders->Insert(topic, &temp_topic_header);

	if (!topic_header)
	{
		// Someone scooped us while we were creating the topic header.
		// Let's use the topic header created by the other actor.
		topic_header = (TopicHeader *) m_TopicHeaders->Find(topic);
	}

	return topic_header;
}

Message::Message(MessageHeader *header, void *payload, bool has_been_published)
	: m_Header(header), m_Payload(payload), m_HasBeenPublished(has_been_published)
{
}

std::string_view Message::GetTopic() const
{
	return m_Header->topic;
}

const Uuid &Message::GetPayloadId() const
{
	return m_Header->payload_id;
}

std::uint64_t Message::GetFrameId() const
{
	return m_Header->frame_id;
}

std::uint16_t Message::GetPartialFrameId() const
{
	return m_Header->partial_frame_id;
}

const Uuid &Message::GetTraceId() const
{
	return m_Header->trace_id;
}

std::string_view Message::GetProducerHostnname() const
{
	return m_Header->producer_hostname;
}

std::uint32_t Message::GetProducerPid() const
{
	return m_Header->producer_pid;
}

std::uint64_t Message::GetProducerTimestamp() const
{
	return m_Header->producer_timestamp;
}

const PayloadInfo &Message::GetPayloadInfo() const
{
	return m_Header->payload_info;
}

const ArrayInfo &Message::GetArrayInfo() const
{
	return m_Header->payload_info.array_info;
}

void Message::SetArrayInfo(const ArrayInfo &array_info)
{
	m_Header->payload_info.array_info = array_info;
}

void *Message::GetPayload() const
{
	return m_Payload;
}

std::size_t Message::GetPayloadSize() const
{
	return m_Header->payload_info.total_size;
}

const MetadataEntry &Message::GetMetadataEntry(std::uint8_t metadata_id) const
{
	return m_Header->metadata_entries[metadata_id];
}

void Message::SetMetadataEntry(std::uint8_t metadata_id, std::uint64_t value)
{
	m_Header->metadata_entries[metadata_id].integer = value;
}

void Message::SetMetadataEntry(std::uint8_t metadata_id, double value)
{
	m_Header->metadata_entries[metadata_id].floating_point = *reinterpret_cast<std::uint64_t *>(&value);
}

void Message::SetMetadataEntry(std::uint8_t metadata_id, std::string_view value)
{
	char *dest = m_Header->metadata_entries[metadata_id].string;
	std::fill(dest, dest + METADATA_MAX_STRLEN, '\0');
	value.copy(dest, METADATA_MAX_STRLEN - 1);
}

const std::uint64_t Message::GetStartByte() const
{
	return m_Header->start_byte;
}

void Message::SetStartByte(std::uint64_t start_byte)
{
	m_Header->start_byte = start_byte;
}

const std::uint64_t Message::GetEndByte() const
{
	return m_Header->end_byte;
}

void Message::SetEndByte(std::uint64_t end_byte)
{
	m_Header->end_byte = end_byte;
}
