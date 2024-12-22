#include "MessageBroker.h"

#include "Util.h"
#include "Timing.h"
#include "HostName.h"

#include <algorithm>

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

	std::copy(header.message_offsets, header.message_offsets + TOPIC_MAX_NUM_MESSAGES, message_offsets);
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

	if (device_id < 0)
	{
		message.m_Payload = m_CpuPayloadMemory->GetAddress(offset);
	}
	else
	{
		message.m_Payload = m_GpuPayloadMemory[device_id]->GetAddress(offset);
	}

	// Allocate a message header.
	auto message_header_handle = m_MessageHeaderAllocator.Allocate();

	if (message_header_handle == PoolAllocator::INVALID_HANDLE)
	{
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
	}
	else
	{
		// Not the first partial frame. Use the same frame ID and increment the partial frame ID.
		message.m_Header->partial_frame_id++;
	}

	// Set the timestamp.
	message.m_Header->producer_timestamp = GetTimeStamp();

	// TODO: put message offsets.

	// Go to synchronization structures and signal them.
	// This includes parent topics.
	for (std::size_t i = 0; i <= topic.size(); ++i)
	{
		std::size_t size = topic.size() - i;

		if (i == 0 || topic[size] == '/')
		{
			auto synchronization = GetSynchronization(topic.substr(0, size));

			if (synchronization)
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
