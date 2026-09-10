#include "MessageBroker.h"

#include <cstring>

#include "LocalMessageBroker.h"

size_t GetTopicDepth(std::string_view topic)
{
	return std::count(topic.begin(), topic.end(), '/');
}

Message::Message(MessageHeader *header, void *payload)
	: m_Header(header), m_Payload(payload)
{
}

std::string_view Message::GetTopic() const
{
	return m_Header->topic;
}

size_t Message::GetTopicDepth() const
{
	return ::GetTopicDepth(GetTopic());
}

const Uuid &Message::GetPayloadId() const
{
	return m_Header->payload_id;
}

std::uint64_t Message::GetMessageId() const
{
	return m_Header->message_ids[GetTopicDepth()];
}

std::uint64_t Message::GetMessageId(size_t depth) const
{
	return m_Header->message_ids[depth];
}

std::uint16_t Message::GetPartialMessageId() const
{
	return m_Header->partial_message_id;
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

MessageSubscription::MessageSubscription(std::shared_ptr<MessageBroker> message_broker, std::string_view topic, std::uint64_t preferred_next_message_id, MessageSubscriptionMode mode)
	: m_MessageBroker(message_broker), m_Topic(topic), m_PreferredNextMessageId(preferred_next_message_id), m_SubscriptionMode(mode), m_TopicDepth(GetTopicDepth(topic))
{
}

std::optional<Message> MessageSubscription::GetNextMessage(double timeout_in_seconds, EventWaitMethod wait_type, void (*error_check)())
{
	auto message = m_MessageBroker->GetNextMessage(m_Topic, m_PreferredNextMessageId, m_SubscriptionMode, timeout_in_seconds, wait_type, error_check);

	if (!message.has_value())
		return message;

	// We are going to return a message. Update our message id for the next call.
	m_PreferredNextMessageId = message->GetMessageId(m_TopicDepth) + 1;

	return message;
}

std::optional<Message> MessageSubscription::TryGetNextMessage()
{
	auto message = m_MessageBroker->TryGetNextMessage(m_Topic, m_PreferredNextMessageId, m_SubscriptionMode);

	if (!message.has_value())
		return message;

	// We are going to return a message. Update our message id for the next call.
	m_PreferredNextMessageId = message->GetMessageId() + 1;

	return message;
}

std::optional<size_t> MessageBroker::GetCurrentMessageId(std::string_view topic)
{
	auto message = GetCurrentMessage(topic);

	if (!message.has_value())
		return std::nullopt;

	return message.value().GetMessageId();
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
	auto message = PrepareMessage(topic, array.info.GetSizeInBytes(), trace_id, memory_block_id);

	// Copy over array and array info.
	std::memcpy(message.m_Payload, array.data, array.info.GetSizeInBytes());
	message.SetArrayInfo(array.info);

	PublishMessage(message);

	return message;
}

MessageSubscription MessageBroker::Subscribe(std::string_view topic, MessageSubscriptionMode mode)
{
	auto current_message = GetCurrentMessage(topic);
	auto starting_message_id = current_message.has_value() ? current_message->GetMessageId() : 0;

	return Subscribe(topic, starting_message_id, mode);
}

MessageSubscription MessageBroker::Subscribe(std::string_view topic, size_t preferred_next_message_id, MessageSubscriptionMode mode)
{
	return MessageSubscription(shared_from_this(), topic, preferred_next_message_id, mode);
}

void MessageBroker::PrintDebugInfo() const
{
}
