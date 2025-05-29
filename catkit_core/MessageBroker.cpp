#include "MessageBroker.h"

#include "Util.h"
#include "Timing.h"
#include "HostName.h"

#include <algorithm>
#include <cstdint>
#include <iostream>

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

MessageBroker::MessageBroker(
	MessageBrokerHeader *header,
	std::shared_ptr<HashMap> topic_headers,
	std::shared_ptr<PoolAllocator> message_header_allocator,
	std::shared_ptr<Event> event,
	std::vector<std::shared_ptr<HybridPoolAllocator>> allocators,
	std::vector<std::shared_ptr<Memory>> memory_blocks
)
	: m_Header(header),
	m_TopicHeaders(std::move(topic_headers)),
	m_MessageHeaderAllocator(std::move(message_header_allocator)),
	m_Event(std::move(event)),
	m_Allocators(std::move(allocators)),
	m_MemoryBlocks(memory_blocks),
	m_MessageHeaders(header->message_headers)
{
}

std::shared_ptr<MessageBroker> MessageBroker::Create(StructStream &stream, std::vector<std::shared_ptr<Memory>> memory_blocks)
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

		*stream.Extract<ShareableType>() = memory_block->GetType();
		memory_block->WriteReference(stream);
	}

	DEBUG_PRINT("Creating object.");

	return std::shared_ptr<MessageBroker>(new MessageBroker(
		header,
		std::move(topic_headers),
		std::move(message_header_allocator),
		std::move(event),
		allocators,
		memory_blocks
	));
}

std::shared_ptr<MessageBroker> MessageBroker::Open(StructStream &stream)
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

	return std::shared_ptr<MessageBroker>(new MessageBroker(
		header,
		std::move(topic_headers),
		std::move(message_header_allocator),
		std::move(event),
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
	Uuid::Generate(&trace_id);

	DEBUG_PRINT("Trace id generated.");

	return PrepareMessage(topic, payload_size, trace_id, memory_block_id);
}

Message MessageBroker::PrepareMessage(std::string_view topic, size_t payload_size, Uuid trace_id, uint8_t memory_block_id)
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

	return Message(header, payload, false);
}

void MessageBroker::PublishMessage(Message &message, bool is_final)
{
	DEBUG_PRINT("Publishing message.");

	if (message.m_HasBeenPublished)
	{
		DEBUG_PRINT("Message has already been published.");

		return;
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

	// Deallocate the message header and payload.
	PoolAllocator::BlockHandle message_header_index = message.m_Header - m_MessageHeaders;
	m_MessageHeaderAllocator->Release(message_header_index);

	allocator->Release(message.m_Header->payload_info.block_handle);

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
}

void MessageBroker::PublishData(std::string_view topic, const void *data, size_t data_size, uint8_t memory_block_id)
{
	Uuid trace_id;
	Uuid::Generate(&trace_id);

	PublishData(topic, data, data_size, trace_id, memory_block_id);
}

void MessageBroker::PublishData(std::string_view topic, const void *data, size_t data_size, Uuid trace_id, uint8_t memory_block_id)
{
	auto message = PrepareMessage(topic, data_size, trace_id, memory_block_id);

	// Copy the data to the payload.
	std::memcpy(message.m_Payload, data, data_size);

	// Set the array information.
	ArrayInfo &array_info = message.m_Header->payload_info.array_info;

	array_info.data_type = 'u';
	array_info.byte_order = '=';
	array_info.item_size = 1;
	array_info.ndim = 1;
	array_info.shape[0] = data_size;
	array_info.strides[0] = 1;

	PublishMessage(message);
}

void MessageBroker::PublishData(std::string_view topic, const Tensor &tensor, uint8_t memory_block_id)
{
	Uuid trace_id;
	Uuid::Generate(&trace_id);

	PublishData(topic, tensor, trace_id, memory_block_id);
}

void MessageBroker::PublishData(std::string_view topic, const Tensor &tensor, Uuid trace_id, uint8_t memory_block_id)
{
	// TODO.
}

std::optional<Message> MessageBroker::TryGetMessage(std::string_view topic, size_t frame_id)
{
	auto topic_header = GetTopicHeader(topic);

	if (!topic_header->IsMessageAvailable(frame_id))
		return std::nullopt;

	return FetchMessage(topic_header, frame_id);
}

Message MessageBroker::FetchMessage(TopicHeader* topic_header, size_t frame_id)
{
	// Assume that the frame is available.
	auto header = &m_MessageHeaders[topic_header->message_headers[frame_id % TOPIC_MAX_NUM_MESSAGES]];
	auto offset = header->payload_info.offset_in_buffer;
	auto memory = GetMemory(header->payload_info.memory_block_id);
	auto payload = memory->GetAddress(offset);

	return Message(header, payload, true);
}

std::optional<Message> MessageBroker::GetNewestMessage(std::string_view topic)
{
	auto topic_header = GetTopicHeader(topic);

	if (topic_header->last_frame_id == 0)
		return std::nullopt;

	auto frame_id = topic_header->last_frame_id - 1;

	return FetchMessage(topic_header, frame_id);
}

ShareableType MessageBroker::GetType() const
{
	return ShareableType::MessageBroker;
}

std::shared_ptr<HybridPoolAllocator> MessageBroker::GetAllocator(uint8_t memory_block_id)
{
	if (memory_block_id >= m_Allocators.size())
	{
		return nullptr;
	}

	return m_Allocators[memory_block_id];
}

bool MessageBroker::IsMessageAvailable(std::string_view topic, size_t frame_id)
{
	auto topic_header = GetTopicHeader(topic);

	return topic_header->IsMessageAvailable(frame_id);
}

bool MessageBroker::WillMessageBeAvailable(std::string_view topic, size_t frame_id)
{
	auto topic_header = GetTopicHeader(topic);

	return topic_header->WillMessageBeAvailable(frame_id);
}

size_t MessageBroker::GetNewestMessageId(std::string_view topic)
{
	auto topic_header = GetTopicHeader(topic);

	return topic_header->GetNewestMessageId();
}

size_t MessageBroker::GetOldestMessageId(std::string_view topic)
{
	auto topic_header = GetTopicHeader(topic);

	return topic_header->GetOldestMessageId();
}

double MessageBroker::GetMessageRate(std::string_view topic)
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

std::vector<std::string> MessageBroker::GetAllMessageTopics()
{
	return m_TopicHeaders->GetAllKeys();
}

MessageSubscription MessageBroker::Subscribe(std::string_view topic, MessageSubscriptionMode mode)
{
	auto topic_header = GetTopicHeader(topic);
	auto starting_frame_id = topic_header->first_frame_id.load(std::memory_order_relaxed);

	return MessageSubscription(shared_from_this(), topic_header, starting_frame_id, mode);
}

MessageSubscription MessageBroker::Subscribe(std::string_view topic, size_t starting_frame_id, MessageSubscriptionMode mode)
{
	auto topic_header = GetTopicHeader(topic);

	return MessageSubscription(shared_from_this(), topic_header, starting_frame_id, mode);
}

std::shared_ptr<Memory> MessageBroker::GetMemory(uint8_t memory_block_id)
{
	if (memory_block_id >= m_MemoryBlocks.size())
	{
		return nullptr;
	}

	return m_MemoryBlocks[memory_block_id];
}

TopicHeader *MessageBroker::GetTopicHeader(std::string_view topic)
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

	temp_topic_header.next_frame_id = 0;
	temp_topic_header.first_frame_id = 0;
	temp_topic_header.last_frame_id = 0;
	temp_topic_header.frame_rate = 0.0;

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

std::uint16_t Message::GetPartialFrameId() const
{
	return m_Header->partial_frame_id;
}

const Uuid &Message::GetTraceId() const
{
	return m_Header->trace_id;
}

std::string_view Message::GetProducerHostname() const
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

MetadataEntry *Message::GetMetadataEntry(std::string_view key, bool create_if_not_exists)
{
	for (size_t i = 0; i < m_Header->num_metadata_entries; i++)
		if (key == std::string_view(m_Header->metadata_entries[i].key.data()))
			return &m_Header->metadata_entries[i];

	if (!create_if_not_exists)
		return nullptr;

	// Create a new entry.
	if (m_Header->num_metadata_entries >= MAX_NUM_METADATA_ENTRIES)
	{
		throw std::range_error("Metadata entries are full.");
	}

	auto entry_id = m_Header->num_metadata_entries++;
	auto entry = &m_Header->metadata_entries[entry_id];

	entry->key.fill('\0');
	key.copy(entry->key.data(), entry->key.size() - 1);

	return entry;
}

void Message::SetMetadataEntry(std::string_view key, std::int64_t value)
{
	auto entry = GetMetadataEntry(key, true);

	entry->type = MetadataType::Integer;
	entry->value.integer = value;
}

void Message::SetMetadataEntry(std::string_view key, double value)
{
	auto entry = GetMetadataEntry(key, true);

	entry->type = MetadataType::Integer;
	entry->value.floating_point = value;
}

void Message::SetMetadataEntry(std::string_view key, std::string_view value)
{
	auto entry = GetMetadataEntry(key, true);

	entry->type = MetadataType::String;
	entry->value.string.fill('\0');
	value.copy(entry->value.string.data(), entry->value.string.size() - 1);
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

MessageSubscription::MessageSubscription(std::shared_ptr<MessageBroker> message_broker, TopicHeader *topic_header, std::uint64_t starting_frame_id, MessageSubscriptionMode mode)
	: m_MessageBroker(message_broker), m_TopicHeader(topic_header), m_NextFrameIdToRead(starting_frame_id), m_SubscriptionMode(mode)
{
}

Message MessageSubscription::GetNextMessage(double timeout_in_seconds, EventWaitMethod wait_type, void (*error_check)())
{
	std::uint64_t frame_id = GetNextMessageId();

	// Check if the frame is available.
	if (m_TopicHeader->IsMessageAvailable(frame_id))
	{
		m_NextFrameIdToRead = frame_id + 1;

		return m_MessageBroker->FetchMessage(m_TopicHeader, frame_id);
	}

	// Otherwise, wait for it.
	m_MessageBroker->m_Event->Wait(timeout_in_seconds, [this, frame_id]() { return m_TopicHeader->last_frame_id > frame_id; }, wait_type, error_check);

	m_NextFrameIdToRead = frame_id + 1;

	return m_MessageBroker->FetchMessage(m_TopicHeader, frame_id);
}

std::optional<Message> MessageSubscription::TryGetNextMessage()
{
	std::uint64_t frame_id = GetNextMessageId();

	// Check if the frame is available.
	if (!m_TopicHeader->IsMessageAvailable(frame_id))
		return std::nullopt;

	m_NextFrameIdToRead = frame_id + 1;

	return m_MessageBroker->FetchMessage(m_TopicHeader, frame_id);
}

std::uint64_t MessageSubscription::GetNextMessageId()
{
	size_t frame_id = m_NextFrameIdToRead;
	size_t newest_frame_id = m_TopicHeader->last_frame_id.load(std::memory_order_relaxed);
	size_t oldest_frame_id = m_TopicHeader->first_frame_id.load(std::memory_order_relaxed);

	if (newest_frame_id != 0)
		newest_frame_id--;

	switch (m_SubscriptionMode)
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
