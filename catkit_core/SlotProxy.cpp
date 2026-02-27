#include "SlotProxy.h"
#include "MessageBroker.h"

#include <stdexcept>

SlotProxy::SlotProxy(std::shared_ptr<MessageBroker> broker, const std::string &service_id, const std::string &slot_name, bool read_only, SlotDataType data_type)
	: m_Broker(broker)
	, m_ServiceId(service_id)
	, m_SlotName(slot_name)
	, m_ReadOnly(read_only)
	, m_DataType(data_type)
	, m_GetTopic(service_id + "/" + slot_name + "/get")
	, m_SetTopic(service_id + "/" + slot_name + "/set")
{
}

nlohmann::json SlotProxy::GetJson() const
{
	if (m_DataType != SlotDataType::Json)
	{
		throw std::runtime_error("Type mismatch: slot '" + m_SlotName + "' is not a Json slot");
	}

	auto msg = m_Broker->GetCurrentMessage(m_GetTopic);

	if (!msg.has_value())
		throw std::runtime_error("No data available for slot '" + m_SlotName + "'");

	auto payload = msg->GetPayload();

	if (!payload.data || payload.info.GetSizeInBytes() == 0)
		throw std::runtime_error("Empty payload for slot '" + m_SlotName + "'");

	char *data = (char *) payload.data;

	try
	{
		return nlohmann::json::parse(data, data + payload.info.GetSizeInBytes());
	}
	catch (const nlohmann::json::exception& e)
	{
		throw std::runtime_error("JSON parse error for slot '" + m_SlotName + "': " + e.what());
	}
}

std::string_view SlotProxy::GetRaw() const
{
	if (m_DataType != SlotDataType::Raw)
	{
		throw std::runtime_error("Type mismatch: slot '" + m_SlotName + "' is not a Raw slot");
	}

	auto msg = m_Broker->GetCurrentMessage(m_GetTopic);

	if (!msg.has_value())
		throw std::runtime_error("No data available for slot '" + m_SlotName + "'");

	auto payload = msg->GetPayload();

	return std::string_view(static_cast<const char*>(payload.data), msg->GetPayloadSize());
}

ArrayView SlotProxy::GetArray() const
{
	if (m_DataType != SlotDataType::Array)
	{
		throw std::runtime_error("Type mismatch: slot '" + m_SlotName + "' is not an Array slot");
	}

	auto msg = m_Broker->GetCurrentMessage(m_GetTopic);

	if (!msg.has_value())
		throw std::runtime_error("No data available for slot '" + m_SlotName + "'");

	return msg->GetPayload();
}

void SlotProxy::Set(const nlohmann::json &data)
{
	if (m_ReadOnly)
	{
		throw std::runtime_error("Slot '" + m_SlotName + "' is read-only");
	}

	if (m_DataType != SlotDataType::Json)
	{
		throw std::runtime_error("Type mismatch: slot '" + m_SlotName + "' is not a Json slot");
	}

	auto json_str = data.dump();

	m_Broker->PublishData(m_SetTopic, json_str.data(), json_str.size());
}

void SlotProxy::Set(std::string_view data)
{
	if (m_ReadOnly)
	{
		throw std::runtime_error("Slot '" + m_SlotName + "' is read-only");
	}

	if (m_DataType != SlotDataType::Raw)
	{
		throw std::runtime_error("Type mismatch: slot '" + m_SlotName + "' is not a Raw slot");
	}

	m_Broker->PublishData(m_SetTopic, data.data(), data.size());
}

void SlotProxy::Set(ArrayView data)
{
	if (m_ReadOnly)
	{
		throw std::runtime_error("Slot '" + m_SlotName + "' is read-only");
	}

	if (m_DataType != SlotDataType::Array)
	{
		throw std::runtime_error("Type mismatch: slot '" + m_SlotName + "' is not an Array slot");
	}

	m_Broker->PublishArray(m_SetTopic, data);
}

MessageSubscription SlotProxy::Subscribe(MessageSubscriptionMode mode)
{
	return m_Broker->Subscribe(m_GetTopic, mode);
}

bool SlotProxy::IsReadOnly() const
{
	return m_ReadOnly;
}

const std::string &SlotProxy::GetSlotName() const
{
	return m_SlotName;
}

SlotDataType SlotProxy::GetDataType() const
{
	return m_DataType;
}
