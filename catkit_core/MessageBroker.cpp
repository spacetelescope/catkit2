#include "MessageBroker.h"

#include "Util.h"
#include "Timing.h"
#include "HostName.h"

#include <algorithm>
#include <cstdint>

template<typename T>
T fetch_max(std::atomic<T> &atom, T value)
{
	T current = atom.load(std::memory_order_relaxed);

	while (current < value && !atom.compare_exchange_weak(current, value, std::memory_order_acq_rel))
	{
	}

	return current;
}

class SubtopicIterator {
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

TopicHeader::TopicHeader(const TopicHeader &header)
{
	CopyFrom(header);
}

TopicHeader &TopicHeader::operator=(const TopicHeader &header)
{
	CopyFrom(header);

	return *this;
}

void TopicHeader::CopyFrom(const TopicHeader &header)
{
	next_frame_id.store(header.next_frame_id.load(std::memory_order_relaxed), std::memory_order_relaxed);
	synchronization = header.synchronization;

	std::copy(header.message_headers, header.message_headers + TOPIC_MAX_NUM_MESSAGES, message_headers);
	std::copy((char *)header.metadata_keys, (char *)header.metadata_keys + sizeof(metadata_keys), (char *)metadata_keys);
}

Message MessageBroker::PrepareMessage(const std::string &topic, size_t payload_size, int8_t device_id)
{
	Uuid trace_id;
	m_UuidGenerator.Generate(trace_id);

	return PrepareMessage(topic, trace_id, payload_size, device_id);
}

Message MessageBroker::PrepareMessage(const std::string &topic, Uuid trace_id, size_t payload_size, int8_t device_id)
{
	Message message;

	message.m_HasBeenPublished = false;
	message.m_MessageBroker = shared_from_this();

	// Allocate a payload.
	auto allocator = GetAllocator(device_id);

	if (allocator == nullptr)
	{
		throw std::runtime_error("Invalid device ID.");
	}

	auto block_handle = allocator->Allocate(payload_size);

	if (block_handle == FreeListAllocator::INVALID_HANDLE)
	{
		throw std::runtime_error("Could not allocate payload.");
	}

	auto offset = allocator->GetOffset(block_handle);

	auto memory = GetMemory(device_id);
	message.m_Payload = memory->GetAddress(offset);

	// Allocate a message header.
	auto message_header_handle = m_MessageHeaderAllocator.Allocate();

	if (message_header_handle == PoolAllocator::INVALID_HANDLE)
	{
		// Deallocate allocated memory block.
		// TODO: Do this with RAII.
		allocator->Deallocate(block_handle);

		throw std::runtime_error("Could not allocate message header.");
	}

	// Access the message header.
	message.m_Header = &m_MessageHeaders[message_header_handle];
	auto header = message.m_Header;

	// Set the payload information.
	header->payload_info.device_id = device_id;
	header->payload_info.total_size = payload_size;
	header->payload_info.offset_in_buffer = offset;
	m_UuidGenerator.Generate(header->payload_id);

	// Set the topic.
	std::strncpy(header->topic, topic.c_str(), sizeof(header->topic));

	// Set the trace ID.
	std::strncpy(header->trace_id, trace_id, sizeof(header->trace_id));

	// Set the producer information.
	std::strncpy(header->producer_hostname, GetHostName().c_str(), sizeof(header->producer_hostname));
	header->producer_pid = GetProcessId();

	header->partial_frame_id = 0;
	header->start_byte = 0;
	header->end_byte = payload_size;

	// Set default values.
	header->frame_id = INVALID_FRAME_ID;
	header->producer_timestamp = 0;

	return message;
}

void MessageBroker::PublishMessage(Message &message, bool is_final)
{
	if (message.m_HasBeenPublished)
	{
		return;
	}

	auto topic = std::string_view(message.m_Header->topic);
	auto topic_header = m_TopicHeaders.Find(topic);

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

	for (const auto &subtopic : SubtopicRange(topic))
	{
		auto topic_header = m_TopicHeaders.Find(std::string(subtopic));

		if (!topic_header)
		{
			// TODO: if the topic header doesn't exist, create it.

		}

		auto synchronization = GetSynchronization(subtopic);

		// Copy over message header reference.
		std::size_t message_header_index = message.m_Header - m_MessageHeaders;
		topic_header->message_headers[message.m_Header->frame_id % TOPIC_MAX_NUM_MESSAGES] = message_header_index;

		{
			// Obtain a lock as we're about to signal the synchronization structure.
			auto lock = SynchronizationLock(synchronization);

			// Make the message available.
			fetch_max(topic_header->last_frame_id, message.m_Header->frame_id);

			// Signal the synchronization structure.
			synchronization->Signal();
		}
	}

	if (!is_final)
	{
		// Copy the message header since it's gone after publishing.
		auto message_header_handle = m_MessageHeaderAllocator.Allocate();

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

std::shared_ptr<FreeListAllocator> MessageBroker::GetAllocator(int8_t device_id)
{
	if (device_id < -1 || device_id >= MAX_NUM_GPUS)
	{
		return nullptr;
	}

	if (device_id == -1)
	{
		return m_CpuPayloadAllocator;
	}

	return m_GpuPayloadAllocator[device_id];
}

std::shared_ptr<Synchronization> MessageBroker::GetSynchronization(std::string_view topic)
{
	auto topic_header = m_TopicHeaders.Find(topic);

	if (topic_header == nullptr)
	{
		return nullptr;
	}

	// Look up the synchronization structure (not the shared data).
	if (m_Synchronizations.find(topic) == m_Synchronizations.end())
	{
		m_Synchronizations[topic] = std::make_shared<Synchronization>(topic_header->synchronization);
	}

	return m_Synchronizations[topic];
}
