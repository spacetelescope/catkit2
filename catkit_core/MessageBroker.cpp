#include "MessageBroker.h"

std::size_t ArrayInfo::GetNumItems() const
{
	std::size_t num_items = 1;

	for (std::size_t i = 0; i < ndim; ++i)
	{
		num_items *= shape[i];
	}

	return num_items;
}

std::size_t ArrayInfo::GetNumBytes() const
{
	std::size_t num_items = GetNumItems();
	return num_items * item_size;
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

