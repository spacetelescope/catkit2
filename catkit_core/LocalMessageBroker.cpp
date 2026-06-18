#include "LocalMessageBroker.h"

#include "Util.h"
#include "Timing.h"
#include "HostName.h"

#include <algorithm>
#include <cstdint>
#include <iostream>
#include <cstring>

// Decay rate for the frame rate estimate in 1/sec.
const double FRAMERATE_DECAY = 2.5;

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

constexpr std::uint64_t AVAILABILITY_BITMAP_MASK = (1 << TOPIC_MAX_NUM_MESSAGES) - 1;

std::tuple<std::size_t, std::uint16_t> unpack_availability(std::uint64_t availability)
{
	return std::make_tuple(availability >> TOPIC_MAX_NUM_MESSAGES, availability & AVAILABILITY_BITMAP_MASK);
}

std::uint64_t pack_availability(std::size_t last_id, std::uint16_t bitmap)
{
	return (last_id << TOPIC_MAX_NUM_MESSAGES) | bitmap;
}

bool TopicHeader::IsMessageAvailable(std::size_t frame_id) const
{
	auto [last, bitmap] = unpack_availability(availability.load(std::memory_order_relaxed));

	// Compute how many messages back from last this frame_id is.
	// last-1 is the newest message, so offset 0 is last-1.
	if (frame_id >= last)
		return false;

	std::size_t offset = last - 1 - frame_id;
	if (offset >= TOPIC_MAX_NUM_MESSAGES)
		return false;

	return (bitmap >> offset) & 1;
}

bool TopicHeader::WillMessageBeAvailable(std::size_t frame_id) const
{
	auto [last, bitmap] = unpack_availability(availability.load(std::memory_order_relaxed));

	// A message will be available if it's in the future (>= last) or currently in the buffer.
	if (frame_id >= last)
		return true;

	// Check if it's currently in the buffer.
	std::size_t offset = last - 1 - frame_id;
	return offset < TOPIC_MAX_NUM_MESSAGES;
}

std::size_t TopicHeader::GetBegin() const
{
	auto [last, bitmap] = unpack_availability(availability.load(std::memory_order_relaxed));

	// Compute first (oldest message ID) from last and bitmap.
	// If last < 16, buffer not full, so first = 0.
	// Otherwise, first = last - 16 + countl_zero(bitmap).
	if (last < TOPIC_MAX_NUM_MESSAGES)
		return 0;

	return last - TOPIC_MAX_NUM_MESSAGES + countl_zero((uint16_t) bitmap);
}

std::size_t TopicHeader::GetEnd() const
{
	auto [last, bitmap] = unpack_availability(availability.load(std::memory_order_relaxed));

	// With relative bitmap:
	// Bit 0 = last - 1 (newest), bit 1 = last - 2, etc.
	// countr_zero(bitmap) = number of trailing zeros = how many newest messages are unavailable
	// end = last - countr_zero(bitmap) = first ID beyond the newest available message
	// Check for underflow: if countr_zero > last, return 0.
	auto trailing_zeros = countr_zero((uint16_t) bitmap);
	if (trailing_zeros > last)
		return 0;

	return last - trailing_zeros;
}

std::size_t TopicHeader::GetNextMessageId(size_t preferred_next_frame_id, MessageSubscriptionMode mode) const
{
	auto [last, bitmap] = unpack_availability(availability.load(std::memory_order_relaxed));

	size_t frame_id = preferred_next_frame_id;

	// Compute oldest and newest from last and bitmap.
	size_t newest_frame_id = (last == 0) ? 0 : last - 1;
	size_t oldest_frame_id;
	if (last < TOPIC_MAX_NUM_MESSAGES)
		oldest_frame_id = 0;
	else
		oldest_frame_id = last - TOPIC_MAX_NUM_MESSAGES + countl_zero((uint16_t) bitmap);

	switch (mode)
	{
		case MessageSubscriptionMode::NewestOnly:

		// If the frame we are aiming to read is not the newest,
		// return the newest frame instead.
		if (newest_frame_id >= frame_id)
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

TopicHeader::ReserveResult TopicHeader::TryReserve(std::size_t message_id)
{
	while (true)
	{
		auto current_availability = availability.load(std::memory_order_relaxed);
		auto [last, bitmap] = unpack_availability(current_availability);

		// Check if the message id is too old (already evicted).
		if (last > TOPIC_MAX_NUM_MESSAGES && message_id < last - TOPIC_MAX_NUM_MESSAGES)
			return {
				.success=false, .can_try_again=false,
				.has_old_message_header=false, .old_message_header=0,
				.message_id = message_id
			};

		// Check if we need to advance last to include this message.
		if (message_id >= last)
		{
			// We can only advance one step at a time since we can only return one evicted header.
			// Check if the message is immediately next (message_id == last).
			if (message_id > last)
			{
				// Message is further ahead. We need to advance step by step.
				// Return failure but indicate caller should retry.
				return {
					.success = false, .can_try_again = true,
					.has_old_message_header = false, .old_message_header = 0,
					.message_id = message_id
				};
			}

			// message_id == last, we can advance by one.
			// Check if we need to evict a message.
			bool was_available = bitmap & (1 << (TOPIC_MAX_NUM_MESSAGES - 1));
			std::size_t slot = last % TOPIC_MAX_NUM_MESSAGES;
			PoolAllocator::BlockHandle message_header = message_headers[slot];

			// Update bitmap and last.
			bitmap <<= 1;
			last++;

			// Try to set the new availability.
			auto new_availability = pack_availability(last, bitmap);
			if (!availability.compare_exchange_strong(current_availability, new_availability, std::memory_order_acq_rel))
			{
				// We failed, try again.
				continue;
			}

			// We succeeded. Check if we reached the target message_id.
			bool success = (last - 1) == message_id;
			return {
				.success = success, .can_try_again = true,
				.has_old_message_header = was_available,
				.old_message_header = message_header,
				.message_id = last - 1
			};
		}
		else
		{
			// Message is in the current window.
			// Compute the bit position for this message.
			std::size_t offset = last - 1 - message_id;

			// Check if this message is already marked.
			if (bitmap & (1 << offset))
			{
				// Message already exists.
				return {
					.success = false, .can_try_again = false,
					.has_old_message_header = false, .old_message_header = 0,
					.message_id = message_id
				};
			}

			// Set the bit for this message.
			bitmap |= (1 << offset);

			// Try to set the new availability.
			auto new_availability = pack_availability(last, bitmap);
			if (!availability.compare_exchange_strong(current_availability, new_availability, std::memory_order_acq_rel))
			{
				// We failed, try again.
				continue;
			}

			// We succeeded so the frame is marked.
			return {
				.success = true, .can_try_again = false,
				.has_old_message_header = false, .old_message_header = 0,
				.message_id = message_id
			};
		}
	}
}

TopicHeader::ReserveResult TopicHeader::TryReserveNext()
{
	while (true)
	{
		auto current_availability = availability.load(std::memory_order_relaxed);
		auto [last, bitmap] = unpack_availability(current_availability);

		// Check if the message in the slot that we're about to evict was available.
		bool was_available = bitmap & (1 << (TOPIC_MAX_NUM_MESSAGES - 1));
		auto slot = last % TOPIC_MAX_NUM_MESSAGES;
		PoolAllocator::BlockHandle message_header = message_headers[slot];

		// Increment last and update bitmap.
		bitmap <<= 1;
		last++;

		// Try to set the new availability.
		auto new_availability = pack_availability(last, bitmap);
		if (!availability.compare_exchange_strong(current_availability, new_availability, std::memory_order_acq_rel))
		{
			// We failed, try again.
			continue;
		}

		// We succeeded so the frame is marked.
		return {
			.success = true, .can_try_again = true,
			.has_old_message_header = was_available, .old_message_header = message_header,
			.message_id = last - 1
		};
	}
}

bool TopicHeader::TryMakeAvailable(std::size_t message_id)
{
	DEBUG_PRINT("TryMakeAvailable " << message_id);

	while (true)
	{
		auto current_availability = availability.load(std::memory_order_relaxed);
		auto [last, bitmap] = unpack_availability(current_availability);

		// If the message is in the future or too old, we cannot make it available (it needs to be reserved first).
		if (message_id >= last)
			return false;

		std::size_t offset = last - 1 - message_id;

		// If the message is too old, we cannot make it available either.
		if (offset >= TOPIC_MAX_NUM_MESSAGES)
			return false;

		// Mark the bit on the bitmap.
		bitmap |= (1 << offset);

		// Try to set the new availability.
		auto new_availability = pack_availability(last, bitmap);
		if (!availability.compare_exchange_strong(current_availability, new_availability, std::memory_order_acq_rel))
		{
			// We failed, try again.
			continue;
		}

		return true;
	}
}

void TopicHeader::UpdateMessageRate(std::uint64_t timestamp)
{
	double time_delta = double(std::int64_t(timestamp) - std::int64_t(last_update)) * 1e-9;

	if (time_delta < 0)
		time_delta = 0;

	last_update = timestamp;
	message_rate = message_rate * std::exp(-FRAMERATE_DECAY * time_delta) + FRAMERATE_DECAY;
}

double TopicHeader::GetMessageRate(std::uint64_t current_timestamp) const
{
	double time_delta = double(std::int64_t(current_timestamp) - std::int64_t(last_update)) * 1e-9;

	if (time_delta < 0)
		time_delta = 0;

	return message_rate * std::exp(-FRAMERATE_DECAY * time_delta);
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
		allocators,
		memory_blocks,
		stream.GetBuffer()
	));
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

std::size_t LocalMessageBroker::CalculateBufferSize()
{
	return 0;
}

Message LocalMessageBroker::PrepareMessageImpl(std::string_view topic, size_t payload_size, Uuid trace_id, uint8_t memory_block_id)
{
	// Allocate a payload.
	auto allocator = GetAllocator(memory_block_id);

	if (allocator == nullptr)
	{
		throw std::runtime_error("Invalid device ID: " + std::to_string(memory_block_id));
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

	header->message_ids.fill(INVALID_MESSAGE_ID);
	header->partial_message_id = 0;
	header->start_byte = 0;
	header->end_byte = payload_size;

	// Reset metadata.
	header->num_metadata_entries = 0;

	DEBUG_PRINT("Header set");

	return Message(header, payload);
}

Message LocalMessageBroker::PublishMessage(Message message, bool is_final)
{
	DEBUG_PRINT("Publishing message.");

	if (message.m_Header == nullptr || message.m_Payload == nullptr)
		throw std::runtime_error("Message is invalid. Use PrepareMessage() to create a valid message.");

	// Set the timestamp.
	auto timestamp = GetTimeStamp();
	message.m_Header->producer_timestamp = timestamp;

	// Save the message header index for later.
	PoolAllocator::BlockHandle message_header_index = message.m_Header - m_MessageHeaders;

	DEBUG_PRINT("Starting to publish the message.");

	auto topic = std::string_view(message.m_Header->topic);
	auto allocator = GetAllocator(message.m_Header->payload_info.memory_block_id);

	size_t i = 0;

	// Reserve a message ID for all subtopics.
	for (const auto &subtopic : SubtopicRange(topic))
	{
		auto topic_header = GetTopicHeader(subtopic);

		DEBUG_PRINT("Reserving ID for topic \"" << subtopic << "\".");

		while (true)
		{
			TopicHeader::ReserveResult reserve_result;

			if (message.m_Header->message_ids[i] == INVALID_MESSAGE_ID)
			{
				reserve_result = topic_header->TryReserveNext();
			}
			else
			{
				reserve_result = topic_header->TryReserve(message.m_Header->message_ids[i]);
			}

			DEBUG_PRINT("ReserveResult: ");
			DEBUG_PRINT("  success: " << reserve_result.success);
			DEBUG_PRINT("  has_old_message_header: " << reserve_result.has_old_message_header);
			DEBUG_PRINT("  can_try_again: " << reserve_result.can_try_again);
			DEBUG_PRINT("  old_message_header: " << reserve_result.old_message_header);
			DEBUG_PRINT("  message_id: " << reserve_result.message_id);

			// Check if we were given a message header to deallocate.
			if (reserve_result.has_old_message_header)
			{
				// Deallocate the old message meader.
				DEBUG_PRINT("Evicting message from topic " << topic);

				// Deallocate the payload.
				auto header = m_MessageHeaders[reserve_result.old_message_header];
				auto removal_allocator = GetAllocator(header.payload_info.memory_block_id);
				removal_allocator->Release(header.payload_info.block_handle);

				// Deallocate the MessageHeader itself.
				m_MessageHeaderAllocator->Release(reserve_result.old_message_header);

				DEBUG_PRINT("Message evicted successfully.");
			}

			if (!reserve_result.success)
			{
				if (reserve_result.can_try_again)
				{
					// We were not successful and since we cannot try again,
					// we will never be successful. This is only an error if this
					// is the deepest topic.
					if (i == 0)
						throw std::runtime_error("Cannot reserve slot in topic.");

					break;
				}
			}

			// We successfully reserved the slot. We can now proceed to publish it.
			message.m_Header->message_ids[i] = reserve_result.message_id;

			// Copy over the message header reference.
			PoolAllocator::BlockHandle message_header_index = message.m_Header - m_MessageHeaders;
			topic_header->message_headers[reserve_result.message_id % TOPIC_MAX_NUM_MESSAGES] = message_header_index;

			m_MessageHeaderAllocator->Acquire(message_header_index);
			allocator->Acquire(message.m_Header->payload_info.block_handle);

			// Note: if something goes wrong, we ignore.
			topic_header->TryMakeAvailable(reserve_result.message_id);

			break;
		}

		// Update framerate on the topic.
		// TODO: put this after the event signaling, since we don't want this in the
		// critical path.
		topic_header->UpdateMessageRate(timestamp);

		// Only publish on the bottom-most topic when it's a partial message.
		if (!is_final)
			break;
	}

	m_Event->Signal();

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

	// Deallocate the old message header and payload.
	m_MessageHeaderAllocator->Release(message_header_index);
	allocator->Release(message.m_Header->payload_info.block_handle);

	// Return either no message or a new message.
	if (is_final)
	{
		return Message(nullptr, nullptr);
	}
	else
	{
		return message;
	}
}

Message LocalMessageBroker::FetchMessage(TopicHeader* topic_header, size_t message_id)
{
	if (message_id == INVALID_MESSAGE_ID)
		throw std::runtime_error("Message ID is not valid.");

	// Assume that the frame is available.
	auto header = &m_MessageHeaders[topic_header->message_headers[message_id % TOPIC_MAX_NUM_MESSAGES]];
	auto offset = header->payload_info.offset_in_buffer;
	auto memory = GetMemory(header->payload_info.memory_block_id);
	auto payload = memory->GetAddress(offset);

	return Message(header, payload);
}

std::optional<Message> LocalMessageBroker::GetCurrentMessage(std::string_view topic)
{
	DEBUG_PRINT("getting current message for " << topic);

	auto topic_header = GetTopicHeader(topic);

	DEBUG_PRINT("topic header: " << topic_header);

	auto last_message_id = topic_header->GetEnd();
	DEBUG_PRINT("last message id: " << last_message_id);

	if (last_message_id == 0)
		return std::nullopt;

	return FetchMessage(topic_header, last_message_id - 1);
}

std::optional<Message> LocalMessageBroker::GetNextMessage(std::string_view topic, size_t preferred_next_message_id, MessageSubscriptionMode mode, double timeout_in_seconds, EventWaitMethod wait_type, void (*error_check)())
{
	auto topic_header = GetTopicHeader(topic);

	std::uint64_t new_message_id = topic_header->GetNextMessageId(preferred_next_message_id, mode);

	DEBUG_PRINT("GetNextMessageId: " << new_message_id);

	// Check if the frame is available.
	if (topic_header->IsMessageAvailable(new_message_id))
	{
		std::cout << "Message is available so returning it." << std::endl;
		return FetchMessage(topic_header, new_message_id);
	}

	// Otherwise, wait for it.
	m_Event->Wait(timeout_in_seconds, [topic_header, new_message_id]() { return topic_header->IsMessageAvailable(new_message_id); }, wait_type, error_check);

	return FetchMessage(topic_header, new_message_id);
}

std::optional<Message> LocalMessageBroker::TryGetNextMessage(std::string_view topic, size_t preferred_next_message_id, MessageSubscriptionMode mode)
{
	auto topic_header = GetTopicHeader(topic);

	std::uint64_t frame_id = topic_header->GetNextMessageId(preferred_next_message_id, mode);

	// Check if the frame is available.
	if (!topic_header->IsMessageAvailable(frame_id))
		return std::nullopt;

	return FetchMessage(topic_header, frame_id);
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

double LocalMessageBroker::GetMessageRate(std::string_view topic)
{
	auto topic_header = GetTopicHeader(topic);
	auto timestamp = GetTimeStamp();

	return topic_header->GetMessageRate(timestamp);
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
	TopicHeader temp_topic_header;

	temp_topic_header.availability = pack_availability(0, 0);
	temp_topic_header.message_rate = 0.0;
	temp_topic_header.last_update = 0;

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

void LocalMessageBroker::PrintDebugInfo() const
{
	auto topics = m_TopicHeaders->GetAllKeys();

	std::cout << "LocalMessageBroker " << this << ":" << std::endl
		<< "  Number of topics: " << topics.size() << " / " << m_TopicHeaders->GetCapacity() << std::endl
		<< "  Message headers: " << m_MessageHeaderAllocator->GetNumUsedBlocks() << " / " << m_MessageHeaderAllocator->GetCapacity() << std::endl
		<< "  Message payloads:" << std::endl;

	size_t i = 0;

	for (auto &alloc : m_Allocators)
	{
		std::cout << "    Block " << i << ": " << alloc->GetUsage() << " / " << alloc->GetCapacity() << std::endl;

		i++;
	}
}
