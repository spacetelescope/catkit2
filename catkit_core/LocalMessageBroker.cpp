#include "LocalMessageBroker.h"

#include "Util.h"
#include "Timing.h"
#include "HostName.h"

#include <algorithm>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <string>
#include <string_view>
#include <type_traits>

// Decay rate for the frame rate estimate in 1/sec.
const double FRAMERATE_DECAY = 2.5;

//#define DEBUG_PRINT(a) std::cout << a << std::endl
#define DEBUG_PRINT(a)

namespace
{
	constexpr std::size_t AlignUp(std::size_t value, std::size_t alignment)
	{
		if (alignment == 0)
			return value;

		const std::size_t remainder = value % alignment;
		return remainder == 0 ? value : value + (alignment - remainder);
	}

	constexpr std::size_t BitWidth(std::size_t value)
	{
		std::size_t width = 0;
		while (value != 0)
		{
			value >>= 1;
			++width;
		}
		return width;
	}

	constexpr std::size_t HashMapEntrySize()
	{
		const std::size_t raw_entry_size = sizeof(std::uint8_t) + TOPIC_MAX_KEY_SIZE + sizeof(TopicHeader);
		return AlignUp(raw_entry_size, alignof(std::atomic<std::uint8_t>));
	}
}

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
		return SubtopicIterator({}, '\0', false);
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

bool TopicHeader::IsMessageAvailable(std::size_t frame_id)
{
	size_t first = first_frame_id.load(std::memory_order_relaxed);
	size_t last = last_frame_id.load(std::memory_order_relaxed);

	return (frame_id >= first) && (frame_id < last);
}

bool TopicHeader::WillMessageBeAvailable(std::size_t frame_id)
{
	size_t first = first_frame_id.load(std::memory_order_relaxed);

	return frame_id >= first;
}

std::size_t TopicHeader::GetOldestMessageId()
{
	return first_frame_id.load(std::memory_order_relaxed);
}

std::size_t TopicHeader::GetNewestMessageId()
{
	size_t last = last_frame_id.load(std::memory_order_relaxed);

	if (last == 0)
		return 0;

	return last - 1;
}

LocalMessageBroker::LocalMessageBroker(
	MessageBrokerHeader *header,
	std::shared_ptr<HashMap> topic_headers,
	std::shared_ptr<PoolAllocator> message_header_allocator,
	std::shared_ptr<Event> event,
	std::vector<std::shared_ptr<HybridPoolAllocator>> allocators,
	std::vector<std::shared_ptr<Memory>> memory_blocks,
	std::shared_ptr<Memory> header_memory
)
	: Shareable(header_memory),
	m_Header(header),
	m_TopicHeaders(std::move(topic_headers)),
	m_MessageHeaderAllocator(std::move(message_header_allocator)),
	m_Event(std::move(event)),
	m_Allocators(std::move(allocators)),
	m_MemoryBlocks(memory_blocks),
	m_MessageHeaders(header->message_headers)
{

}

std::shared_ptr<LocalMessageBroker> LocalMessageBroker::Create(StructStream &stream, std::vector<std::shared_ptr<Memory>> memory_blocks)
{
	DEBUG_PRINT("Creating message broker");

	*stream.Extract<std::array<std::uint8_t, 4>>() = MESSAGE_BROKER_VERSION;

	DEBUG_PRINT("Written version.");

	auto header = stream.Extract<MessageBrokerHeader>();

	GetHostName().copy(header->creator_hostname, HOST_NAME_SIZE);
	header->time_of_creation = GetTimeStamp();
	header->creator_pid = GetProcessId();
	header->num_memory_blocks = memory_blocks.size();

	header->time_of_last_activity = GetTimeStamp();

	DEBUG_PRINT("Extracted static parts.");

	auto topic_headers = HashMap::Create(stream, TOPIC_HASH_MAP_SIZE, TOPIC_MAX_KEY_SIZE, sizeof(TopicHeader));

	auto message_header_allocator = PoolAllocator::Create(stream, MAX_NUM_MESSAGES);

	std::string id = "catkit2_message_broker_" + std::to_string(header->creator_pid) + "_" + std::to_string(header->time_of_creation);
	auto event = Event::Create(stream, id);

	DEBUG_PRINT("Extracting allocators.");

	std::vector<std::shared_ptr<HybridPoolAllocator>> allocators;

	for (auto memory_block : memory_blocks)
	{
		auto capacity = memory_block->GetCapacity();
		capacity = round_down_to_power_of_2(capacity);

		std::shared_ptr<HybridPoolAllocator> allocator = HybridPoolAllocator::Create(stream, capacity, MEMORY_ALIGNMENT, MIN_SIZE_POOL);

		allocators.push_back(std::move(allocator));

		*stream.Extract<MemoryType>() = memory_block->GetMemoryType();
		memory_block->WriteReference(&stream);
	}

	DEBUG_PRINT("Creating object.");

	return std::shared_ptr<LocalMessageBroker>(new LocalMessageBroker(
		header,
		std::move(topic_headers),
		std::move(message_header_allocator),
		std::move(event),
		std::move(allocators),
		memory_blocks,
		stream.GetBuffer()
	));
}

std::shared_ptr<LocalMessageBroker> LocalMessageBroker::Create(std::string_view broker_name, std::vector<std::shared_ptr<Memory>> memory_blocks)
{
	std::string header_name = std::string(broker_name) + ".hdr";

	std::size_t required_size = CalculateBufferSize(memory_blocks);
	required_size = AlignUp(required_size, MEMORY_ALIGNMENT);
	required_size = std::max<std::size_t>(required_size, 1ull << 20); // Minimum 1 MiB header.

	for (std::size_t attempt = 0; attempt < 8; ++attempt)
	{
		std::shared_ptr<SharedMemory> header_shared_memory = SharedMemory::Create(header_name, required_size);

		try
		{
			auto stream = StructStream(header_shared_memory);
			return LocalMessageBroker::Create(stream, memory_blocks);
		}
		catch (const std::runtime_error &ex)
		{
			header_shared_memory->Destroy();
			header_shared_memory.reset();

			std::string_view message(ex.what());
			if (message.find("StructStream::Extract exceeded buffer capacity") == std::string_view::npos)
				throw;

			required_size = AlignUp(required_size * 3 / 2, MEMORY_ALIGNMENT);
		}
	}

	throw std::runtime_error("Failed to allocate sufficient header memory for LocalMessageBroker");
}

std::shared_ptr<LocalMessageBroker> LocalMessageBroker::Open(StructStream &stream)
{
	CheckVersion(stream, MESSAGE_BROKER_VERSION);

	auto header = stream.Extract<MessageBrokerHeader>();

	auto topic_headers = HashMap::Open(stream);
	auto message_header_allocator = PoolAllocator::Open(stream);
	auto event = Event::Open(stream);

	std::vector<std::shared_ptr<HybridPoolAllocator>> allocators;
	std::vector<std::shared_ptr<Memory>> memory_blocks;

	for (std::size_t i = 0; i < header->num_memory_blocks; ++i)
	{
		auto allocator = HybridPoolAllocator::Open(stream);
		allocators.push_back(std::move(allocator));

		MemoryType type = *stream.Extract<MemoryType>();
		switch (type)
		{
			case MemoryType::SharedMemory:
				memory_blocks.push_back(SharedMemory::Open(stream));
				break;
			case MemoryType::LocalMemory:
				memory_blocks.push_back(LocalMemory::Open(stream));
				break;
			default:
				throw std::runtime_error("Unknown memory type.");
		}
	}

	return std::shared_ptr<LocalMessageBroker>(new LocalMessageBroker(
		header,
		std::move(topic_headers),
		std::move(message_header_allocator),
		std::move(event),
		allocators,
		memory_blocks,
		stream.GetBuffer()
	));
}

std::size_t LocalMessageBroker::CalculateBufferSize(const std::vector<std::shared_ptr<Memory>> &memory_blocks, std::size_t initial_offset)
{
	auto advance = [](std::size_t &offset, std::size_t alignment, std::size_t size)
	{
		offset = AlignUp(offset, alignment);
		offset += size;
	};

	std::size_t offset = initial_offset;

	advance(offset, alignof(std::array<std::uint8_t, 4>), sizeof(std::array<std::uint8_t, 4>));
	advance(offset, alignof(MessageBrokerHeader), sizeof(MessageBrokerHeader));

	for (int i = 0; i < 3; ++i)
		advance(offset, alignof(std::size_t), sizeof(std::size_t));
	offset = AlignUp(offset, alignof(std::atomic<std::uint8_t>));
	advance(offset, 1, HashMapEntrySize() * TOPIC_HASH_MAP_SIZE);

	offset = AlignUp(offset, alignof(PoolAllocator::BlockHandle));
	advance(offset, alignof(std::array<std::uint8_t, 4>), sizeof(std::array<std::uint8_t, 4>));
	advance(offset, alignof(std::uint32_t), sizeof(std::uint32_t));
	advance(offset, alignof(std::atomic<PoolAllocator::BlockHandle>), sizeof(std::atomic<PoolAllocator::BlockHandle>));
	advance(offset, alignof(std::atomic<PoolAllocator::BlockHandle>), sizeof(std::atomic<PoolAllocator::BlockHandle>) * MAX_NUM_MESSAGES);
	advance(offset, alignof(std::atomic_size_t), sizeof(std::atomic_size_t) * MAX_NUM_MESSAGES);

	advance(offset, alignof(std::array<std::uint8_t, 4>), sizeof(std::array<std::uint8_t, 4>));
	advance(offset, alignof(std::max_align_t), Event::GetSharedStateSize());

	const std::size_t allocator_min_size = std::min<std::size_t>(MIN_SIZE_POOL, MEMORY_ALIGNMENT * 64);

	for (const auto &memory_block : memory_blocks)
	{
		if (!memory_block)
			continue;

		const std::size_t capacity = round_down_to_power_of_2(memory_block->GetCapacity());

		advance(offset, alignof(std::array<std::uint8_t, 4>), sizeof(std::array<std::uint8_t, 4>));
		advance(offset, alignof(std::size_t), sizeof(std::size_t));
		advance(offset, alignof(std::size_t), sizeof(std::size_t));
		advance(offset, alignof(std::size_t), sizeof(std::size_t));

		advance(offset, alignof(std::array<std::uint8_t, 4>), sizeof(std::array<std::uint8_t, 4>));
		advance(offset, alignof(std::size_t), sizeof(std::size_t));
		advance(offset, alignof(std::size_t), sizeof(std::size_t));

		const std::size_t ratio = std::max<std::size_t>(std::size_t(1), capacity / allocator_min_size);
		const std::size_t depth = BitWidth(ratio) ? BitWidth(ratio) - 1 : 0;
		const std::size_t node_count = 1ull << (depth + 1);

		advance(offset, alignof(std::atomic_uint16_t), sizeof(std::atomic_uint16_t) * node_count);
		advance(offset, alignof(std::atomic_size_t), sizeof(std::atomic_size_t) * (depth + 1));

		advance(offset, HybridPoolAllocator::PoolAlignment(), HybridPoolAllocator::PoolStorageSize() * node_count);

		advance(offset, alignof(MemoryType), sizeof(MemoryType));

		switch (memory_block->GetMemoryType())
		{
			case MemoryType::SharedMemory:
				advance(offset, alignof(char), SHARED_MEMORY_FNAME_SIZE);
				break;
			case MemoryType::LocalMemory:
				advance(offset, alignof(char *), sizeof(char *));
				advance(offset, alignof(std::size_t), sizeof(std::size_t));
				advance(offset, alignof(int), sizeof(int));
				break;
			default:
				throw std::runtime_error("Unsupported memory type when calculating LocalMessageBroker header size.");
		}
	}

	return offset;
}

Message LocalMessageBroker::PrepareMessageImpl(std::string_view topic, size_t payload_size, Uuid trace_id, uint8_t memory_block_id)
{

	
	// Allocate a payload.
	auto allocator = GetAllocator(memory_block_id);

	if (allocator == nullptr)
	{
		throw std::runtime_error("Invalid device ID.");
	}

	DEBUG_PRINT("Gotten allocator.");

	auto block_handle = allocator->Allocate(payload_size);

	if (block_handle == HybridPoolAllocator::INVALID_HANDLE)
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
		allocator->Release(block_handle);

		throw std::runtime_error("Could not allocate message header.");
	}

	// Access the message header.
	auto header = &m_MessageHeaders[message_header_handle];

	DEBUG_PRINT("Message header gotten.");

	// Set the payload information.
	header->payload_info.memory_block_id = memory_block_id;
	header->payload_info.block_handle = block_handle;
	header->payload_info.total_size = payload_size;
	header->payload_info.offset_in_buffer = offset;

	Uuid::Generate(&header->payload_id);

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
	header->producer_timestamp = 0;

	header->partial_frame_id = 0;
	header->start_byte = 0;
	header->end_byte = payload_size;

	// Reset metadata.
	header->num_metadata_entries = 0;

	DEBUG_PRINT("Header set");

	return Message(header, payload, INVALID_FRAME_ID, false);
}

Message LocalMessageBroker::PublishMessage(Message message, bool is_final)
{
	DEBUG_PRINT("Publishing message.");

	if (message.m_HasBeenPublished)
	{
		return message;
	}

	// Set the timestamp.
	message.m_Header->producer_timestamp = GetTimeStamp();

	DEBUG_PRINT("Starting to publish the message.");

	auto topic = std::string_view(message.m_Header->topic);
	auto allocator = GetAllocator(message.m_Header->payload_info.memory_block_id);

	// Publish the message to all subtopics.
	for (const auto &subtopic : SubtopicRange(topic))
	{
		auto topic_header = GetTopicHeader(subtopic);

		DEBUG_PRINT("Publishing to subtopic \"" << subtopic << "\".");

		std::uint64_t first_id = topic_header->first_frame_id.load(std::memory_order_relaxed);

		std::uint64_t frame_id;
		if (message.m_Header->partial_frame_id == 0)
		{
			// Get a frame ID.
			frame_id = topic_header->next_frame_id.fetch_add(1, std::memory_order_relaxed);
		}
		else
		{
			frame_id = topic_header->last_frame_id.load(std::memory_order_relaxed) - 1;
			message.m_Header->partial_frame_id++;
		}

		// Check if we need to remove an old frame from the topic.
		if (frame_id - first_id >= TOPIC_MAX_NUM_MESSAGES)
		{
			DEBUG_PRINT("We need to remove a frame.");

			while (true)
			{
				auto frame_to_remove = topic_header->first_frame_id.load(std::memory_order_relaxed);

				auto message_handle = topic_header->message_headers[frame_to_remove % TOPIC_MAX_NUM_MESSAGES];

				if (!topic_header->first_frame_id.compare_exchange_weak(frame_to_remove, frame_to_remove + 1))
				{
					// We failed, so someone else interrupted us while we were trying to deallocate
					// the message. We need to try again.
					continue;
				}

				DEBUG_PRINT("Removing frame " << frame_to_remove << " from topic " << topic);

				// Deallocate the payload.
				auto header = m_MessageHeaders[message_handle];
				auto removal_allocator = GetAllocator(header.payload_info.memory_block_id);
				removal_allocator->Release(header.payload_info.block_handle);

				// Deallocate the MessageHeader itself.
				m_MessageHeaderAllocator->Release(message_handle);

				DEBUG_PRINT("Frame deleted.");

				break;
			}
		}

		// Copy over message header reference.
		PoolAllocator::BlockHandle message_header_index = message.m_Header - m_MessageHeaders;
		topic_header->message_headers[frame_id % TOPIC_MAX_NUM_MESSAGES] = message_header_index;

		m_MessageHeaderAllocator->Acquire(message_header_index);
		allocator->Acquire(message.m_Header->payload_info.block_handle);

		// Make the message available.
		fetch_max(topic_header->last_frame_id, frame_id + 1);

		// Update the timestamp of last publish for this topic
		// This is used to detect when a remote service has crashed
		topic_header->last_publish_time.store(GetTimeStamp(), std::memory_order_relaxed);
		
		// Mark that this topic has published at least one message
		topic_header->has_published_message.store(true, std::memory_order_relaxed);

		// Update the framerate counter for this topic.
		// TODO: put this after the event signaling, since we don't want this in the
		// critical path.
		if (frame_id > 0)
		{
			auto prev_message_header_id = topic_header->message_headers[(frame_id - 1) % TOPIC_MAX_NUM_MESSAGES];

			std::uint64_t last_timestamp = m_MessageHeaders[prev_message_header_id].producer_timestamp;
			double time_delta = double(std::int64_t(message.m_Header->producer_timestamp) - std::int64_t(last_timestamp)) * 1e-9;

			if (time_delta < 0)
				time_delta = 0;

			topic_header->frame_rate = topic_header->frame_rate * std::exp(-FRAMERATE_DECAY * time_delta) + FRAMERATE_DECAY;
		}

		// If the message is not final, only the bottom-level topic is updated.
		if (!is_final)
			break;
	}

	m_Event->Signal();

	if (!is_final)
	{
		// For non-final messages, deallocate the message header and payload.
		PoolAllocator::BlockHandle message_header_index = message.m_Header - m_MessageHeaders;
		m_MessageHeaderAllocator->Release(message_header_index);
		allocator->Release(message.m_Header->payload_info.block_handle);
	}

	if (!is_final)
	{
		DEBUG_PRINT("Allocating a new message header, since the message is not final.");

		// Copy the message header since it's gone after publishing.
		auto message_header_handle = m_MessageHeaderAllocator->Allocate();

		if (message_header_handle == PoolAllocator::INVALID_HANDLE)
		{
			throw std::runtime_error("Could not allocate message header.");
		}

		auto new_message_header = &m_MessageHeaders[message_header_handle];
		*new_message_header = *message.m_Header;
		message.m_Header = new_message_header;

		DEBUG_PRINT("Copied message header.");
	}

	message.m_HasBeenPublished = is_final;

	return message;
}

std::optional<Message> LocalMessageBroker::TryGetMessage(std::string_view topic, size_t frame_id)
{
	auto topic_header = GetTopicHeader(topic);

	if (!topic_header->IsMessageAvailable(frame_id))
		return std::nullopt;

	return FetchMessage(topic_header, frame_id);
}

Message LocalMessageBroker::FetchMessage(TopicHeader* topic_header, size_t frame_id)
{
	// Assume that the frame is available.
	auto header = &m_MessageHeaders[topic_header->message_headers[frame_id % TOPIC_MAX_NUM_MESSAGES]];
	auto offset = header->payload_info.offset_in_buffer;
	auto memory = GetMemory(header->payload_info.memory_block_id);
	auto payload = memory->GetAddress(offset);


	return Message(header, payload, frame_id, true);
}

std::uint64_t LocalMessageBroker::GetNextMessageId(TopicHeader *topic_header, size_t preferred_next_frame_id, MessageSubscriptionMode mode)
{
	size_t frame_id = preferred_next_frame_id;
	size_t newest_frame_id = topic_header->last_frame_id.load(std::memory_order_relaxed);
	size_t oldest_frame_id = topic_header->first_frame_id.load(std::memory_order_relaxed);

	if (newest_frame_id != 0)
		newest_frame_id--;

	switch (mode)
	{
		case MessageSubscriptionMode::NewestOnly:

		// If the frame we are aiming to read is not the newest,
		// return the newest frame instead.
		if (newest_frame_id > frame_id)
			frame_id = newest_frame_id;

		break;

		case MessageSubscriptionMode::Sequential:

		// If the frame was discarded already,
		// return the oldest available frame instead.
		if (frame_id < oldest_frame_id)
			frame_id = oldest_frame_id;

		break;
	}

	return frame_id;
}

std::optional<Message> LocalMessageBroker::GetCurrentMessage(std::string_view topic)
{
	auto topic_header = GetTopicHeader(topic);
	auto last = topic_header->last_frame_id.load(std::memory_order_relaxed);


	if (last == 0)
		return std::nullopt;

	auto frame_id = last - 1;

	return FetchMessage(topic_header, frame_id);
}

std::optional<Message> LocalMessageBroker::GetNextMessage(std::string_view topic, size_t preferred_next_frame_id, MessageSubscriptionMode mode, double timeout_in_seconds, EventWaitMethod wait_type, void (*error_check)())
{
	auto topic_header = GetTopicHeader(topic);

	std::uint64_t new_frame_id = GetNextMessageId(topic_header, preferred_next_frame_id, mode);

	// Check if the frame is available.
	if (topic_header->IsMessageAvailable(new_frame_id))
		return FetchMessage(topic_header, new_frame_id);

	// Detect service inactivity:
	// If we're waiting for a new message but the service hasn't published anything
	// for a long time, the service is likely dead.
	// This prevents returning stale messages when a remote service has crashed.
	// NOTE: This timeout is very conservative - it should only trigger if a service
	// that was previously publishing messages suddenly stops.
	// Timestamps are in nanoseconds, so 300 seconds = 300e9 nanoseconds
	const double SERVICE_DEAD_TIMEOUT = 300.0 * 1e9; // 5 minutes in nanoseconds
	double last_publish_time = topic_header->last_publish_time.load(std::memory_order_relaxed);
	double current_time = GetTimeStamp();
	
	// Only trigger inactivity detection if we've already received at least one message
	// (meaning we're waiting for a follow-up, not the initial message)
	bool has_published = topic_header->has_published_message.load(std::memory_order_relaxed);
	if (has_published && 
	    last_publish_time > 0 && 
	    (current_time - last_publish_time) > SERVICE_DEAD_TIMEOUT)
	{
		// Service appears to be dead or not publishing
		throw std::runtime_error(
			std::string("Service appears to be inactive on topic '") +
			std::string(topic) + 
			"'. Last message received " + 
			std::to_string((current_time - last_publish_time) / 1e9) +
			" seconds ago. Check if remote service has crashed."
		);
	}

	// Otherwise, wait for it.
	m_Event->Wait(timeout_in_seconds, [topic_header, new_frame_id]() { return topic_header->last_frame_id > new_frame_id; }, wait_type, error_check);

	// Check again after wait completes
	last_publish_time = topic_header->last_publish_time.load(std::memory_order_relaxed);
	current_time = GetTimeStamp();
	has_published = topic_header->has_published_message.load(std::memory_order_relaxed);
	if (has_published &&
	    last_publish_time > 0 && 
	    (current_time - last_publish_time) > SERVICE_DEAD_TIMEOUT)
	{
		throw std::runtime_error(
			std::string("Service appears to be inactive on topic '") +
			std::string(topic) + 
			"'. Last message received " + 
			std::to_string((current_time - last_publish_time) / 1e9) +
			" seconds ago. Check if remote service has crashed."
		);
	}

	return FetchMessage(topic_header, new_frame_id);
}

std::optional<Message> LocalMessageBroker::TryGetNextMessage(std::string_view topic, size_t preferred_next_frame_id, MessageSubscriptionMode mode)
{
	auto topic_header = GetTopicHeader(topic);

	std::uint64_t frame_id = GetNextMessageId(topic_header, preferred_next_frame_id, mode);

	// Check if the frame is available.
	if (!topic_header->IsMessageAvailable(frame_id))
		return std::nullopt;

	auto next_frame_id = topic_header->next_frame_id.load(std::memory_order_relaxed);
	if (frame_id >= next_frame_id)
		return std::nullopt;

	std::size_t slot = frame_id % TOPIC_MAX_NUM_MESSAGES;
	auto message_handle = topic_header->message_headers[slot];
	if (message_handle == PoolAllocator::INVALID_HANDLE)
		return std::nullopt;

	if (message_handle >= MAX_NUM_MESSAGES)
		return std::nullopt;

	auto &message_header = m_MessageHeaders[message_handle];

	if (message_header.payload_info.memory_block_id >= m_MemoryBlocks.size())
		return std::nullopt;

	if (message_header.payload_info.block_handle == HybridPoolAllocator::INVALID_HANDLE)
		return std::nullopt;

	if (message_header.payload_info.total_size == 0)
		return std::nullopt;

	const auto &array_info = message_header.payload_info.array_info;
	if (array_info.item_size == 0 && array_info.ndim == 0)
		return std::nullopt;

	if (message_header.topic[0] == '\0')
		return std::nullopt;

	auto message = FetchMessage(topic_header, frame_id);
	message.m_FrameId = frame_id;
	const auto &info = message.GetArrayInfo();

	return message;
}

ShareableType LocalMessageBroker::GetType() const
{
	return ShareableType::LocalMessageBroker;
}

std::shared_ptr<HybridPoolAllocator> LocalMessageBroker::GetAllocator(uint8_t memory_block_id)
{
	if (memory_block_id >= m_Allocators.size())
	{
		return nullptr;
	}

	return m_Allocators[memory_block_id];
}

bool LocalMessageBroker::IsMessageAvailable(std::string_view topic, size_t frame_id)
{
	auto topic_header = GetTopicHeader(topic);

	return topic_header->IsMessageAvailable(frame_id);
}

bool LocalMessageBroker::WillMessageBeAvailable(std::string_view topic, size_t frame_id)
{
	auto topic_header = GetTopicHeader(topic);

	return topic_header->WillMessageBeAvailable(frame_id);
}

size_t LocalMessageBroker::GetNewestMessageId(std::string_view topic)
{
	auto topic_header = GetTopicHeader(topic);

	return topic_header->GetNewestMessageId();
}

size_t LocalMessageBroker::GetOldestMessageId(std::string_view topic)
{
	auto topic_header = GetTopicHeader(topic);

	return topic_header->GetOldestMessageId();
}

double LocalMessageBroker::GetMessageRate(std::string_view topic)
{
	auto topic_header = GetTopicHeader(topic);
	auto last_message_header_id = topic_header->message_headers[(topic_header->last_frame_id - 1) % TOPIC_MAX_NUM_MESSAGES];
	auto last_timestamp = m_MessageHeaders[last_message_header_id].producer_timestamp;

	auto timestamp = GetTimeStamp();

	double time_delta = double(std::int64_t(timestamp) - std::int64_t(last_timestamp)) * 1e-9;

	if (time_delta < 0)
		time_delta = 0;

	return topic_header->frame_rate * std::exp(-FRAMERATE_DECAY * time_delta);
}

std::vector<std::string> LocalMessageBroker::GetAllMessageTopics()
{
	return m_TopicHeaders->GetAllKeys();
}

std::shared_ptr<Memory> LocalMessageBroker::GetMemory(uint8_t memory_block_id)
{
	if (memory_block_id >= m_MemoryBlocks.size())
	{
		return nullptr;
	}

	return m_MemoryBlocks[memory_block_id];
}

TopicHeader *LocalMessageBroker::GetTopicHeader(std::string_view topic)
{
	DEBUG_PRINT("Getting a topic header for " << topic);

	auto topic_header = (TopicHeader *) m_TopicHeaders->Find(topic);

	if (topic_header)
	{
		DEBUG_PRINT("Found a topic header!");
		return topic_header;
	}

	DEBUG_PRINT("Topic header not found: creating a new one.");

	// The topic header doesn't exist, so create it.
	TopicHeader temp_topic_header{};

	temp_topic_header.next_frame_id = 0;
	temp_topic_header.first_frame_id = 0;
	temp_topic_header.last_frame_id = 0;
	temp_topic_header.frame_rate = 0.0;
	temp_topic_header.message_headers.fill(PoolAllocator::INVALID_HANDLE);
	// Initialize last_publish_time to 0 (invalid) - will be set on first publish
	// This prevents false positives on newly created topics
	temp_topic_header.last_publish_time.store(0.0, std::memory_order_relaxed);
	// Mark as not having published any messages yet
	temp_topic_header.has_published_message.store(false, std::memory_order_relaxed);

	topic_header = (TopicHeader *) m_TopicHeaders->Insert(topic, &temp_topic_header);

	if (!topic_header)
	{
		DEBUG_PRINT("Someone else created it before us.");

		// Someone scooped us while we were creating the topic header.
		// Let's use the topic header created by the other actor.
		topic_header = (TopicHeader *) m_TopicHeaders->Find(topic);
	}
	DEBUG_PRINT("Created a topic header!");

	return topic_header;
}
