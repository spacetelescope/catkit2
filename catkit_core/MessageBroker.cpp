#include "MessageBroker.h"

#include <cstring>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <typeinfo>

#include "LocalMessageBroker.h"

Message::Message(MessageHeader *header, void *payload, std::uint64_t frame_id, bool has_been_published)
	: m_Header(header), m_Payload(payload), m_FrameId(frame_id), m_HasBeenPublished(has_been_published)
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
	return m_FrameId;
}

void Message::SetFrameId(std::uint64_t frame_id)
{
	m_FrameId = frame_id;
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

ArrayView Message::GetPayload() const
{
	return {m_Header->payload_info.array_info, m_Payload};
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

std::size_t Message::GetNumMetadataEntries() const
{
	return m_Header->num_metadata_entries;
}

const MetadataEntry &Message::GetMetadataEntry(std::size_t index) const
{
	if (index >= m_Header->num_metadata_entries)
		throw std::out_of_range("Metadata index out of range");

	return m_Header->metadata_entries[index];
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

MessageSubscription::MessageSubscription(std::shared_ptr<MessageBroker> message_broker, std::string_view topic, std::uint64_t preferred_next_frame_id, MessageSubscriptionMode mode)
	: m_MessageBroker(message_broker), m_Topic(topic), m_PreferredNextFrameId(preferred_next_frame_id), m_SubscriptionMode(mode)
{
}

std::optional<Message> MessageSubscription::GetNextMessage(double timeout_in_seconds, EventWaitMethod wait_type, void (*error_check)())
{
	auto message = m_MessageBroker->GetNextMessage(m_Topic, m_PreferredNextFrameId, m_SubscriptionMode, timeout_in_seconds, wait_type, error_check);

	if (!message.has_value())
		return message;

	// We are going to return a message. Update our frame id for the next call.
	m_PreferredNextFrameId = message->GetFrameId() + 1;

	return message;
}

std::optional<Message> MessageSubscription::TryGetNextMessage()
{
	auto message = m_MessageBroker->TryGetNextMessage(m_Topic, m_PreferredNextFrameId, m_SubscriptionMode);

	if (!message.has_value())
	{
		return message;
	}

	auto frame_id = message->GetFrameId();
	auto topic = m_Topic;

	// Refresh message from local broker if available
	if (auto local_broker = std::dynamic_pointer_cast<LocalMessageBroker>(m_MessageBroker))
	{
		if (auto refreshed = local_broker->TryGetMessage(topic, frame_id))
		{
			message = std::move(refreshed);
		}
	}

	// Validate frame ID
	constexpr std::uint64_t FRAME_ID_SANITY_LIMIT = std::uint64_t(1) << 40; // ~1e12
	bool frame_id_invalid = (frame_id == INVALID_FRAME_ID) || (frame_id > FRAME_ID_SANITY_LIMIT);
	if (frame_id_invalid)
	{
		frame_id = m_PreferredNextFrameId;
		message->SetFrameId(frame_id);
	}

	// We are going to return a message. Update our frame id for the next call.
	m_PreferredNextFrameId = frame_id + 1;

	return message;
}

Message MessageBroker::PrepareMessage(std::string_view topic, size_t payload_size, uint8_t memory_block_id)
{
	Uuid trace_id;
	Uuid::Generate(&trace_id);

	return PrepareMessageImpl(topic, payload_size, trace_id, memory_block_id);
}

Message MessageBroker::PrepareMessage(std::string_view topic, size_t payload_size, Uuid trace_id, uint8_t memory_block_id)
{
	return PrepareMessageImpl(topic, payload_size, trace_id, memory_block_id);
}

Message MessageBroker::PublishData(std::string_view topic, const void *data, size_t data_size, uint8_t memory_block_id)
{
	Uuid trace_id;
	Uuid::Generate(&trace_id);

	return PublishData(topic, data, data_size, trace_id, memory_block_id);
}

Message MessageBroker::PublishData(std::string_view topic, const void *data, size_t data_size, Uuid trace_id, uint8_t memory_block_id)
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

	return message;
}

Message MessageBroker::PublishArray(std::string_view topic, ArrayView array, uint8_t memory_block_id)
{
	Uuid trace_id;
	Uuid::Generate(&trace_id);

	return PublishArray(topic, array, trace_id, memory_block_id);
}

Message MessageBroker::PublishArray(std::string_view topic, ArrayView array, Uuid trace_id, uint8_t memory_block_id)
{
	auto payload_bytes = array.info.GetSizeInBytes();
	auto message = PrepareMessage(topic, payload_bytes, trace_id, memory_block_id);

	// Copy over array and array info.
	std::memcpy(message.m_Payload, array.data, payload_bytes);
	message.SetArrayInfo(array.info);

	PublishMessage(message);

	return message;
}

MessageSubscription MessageBroker::Subscribe(std::string_view topic, MessageSubscriptionMode mode)
{
	auto current_message = GetCurrentMessage(topic);
	auto starting_frame_id = current_message.has_value() ? current_message->GetFrameId() : 0;
	auto shared_self = shared_from_this();
	std::shared_ptr<MessageBroker> broker_ptr(shared_self, this);

	return MessageSubscription(broker_ptr, topic, starting_frame_id, mode);
}

MessageSubscription MessageBroker::Subscribe(std::string_view topic, size_t preferred_next_frame_id, MessageSubscriptionMode mode)
{
	auto shared_self = shared_from_this();
	std::shared_ptr<MessageBroker> broker_ptr(shared_self, this);
	return MessageSubscription(broker_ptr, topic, preferred_next_frame_id, mode);
}
