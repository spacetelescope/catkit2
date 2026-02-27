#include "SlotProxy.h"
#include "MessageBroker.h"
#include "Timing.h"

#include <stdexcept>
#include <chrono>
#include <thread>

// Custom exception classes
class SlotTimeoutError : public std::runtime_error {
public:
	SlotTimeoutError(const std::string &msg) : std::runtime_error(msg) {}
};

class SlotSetterError : public std::runtime_error {
public:
	SlotSetterError(const std::string &msg) : std::runtime_error(msg) {}
};

class SlotCancelledError : public std::runtime_error {
public:
	SlotCancelledError(const std::string &msg) : std::runtime_error(msg) {}
};

SlotProxy::SlotProxy(std::shared_ptr<MessageBroker> broker, const std::string &service_id, const std::string &slot_name, bool read_only, SlotDataType data_type)
	: m_Broker(broker)
	, m_ServiceId(service_id)
	, m_SlotName(slot_name)
	, m_ReadOnly(read_only)
	, m_DataType(data_type)
	, m_BaseTopic(service_id + "/" + slot_name)
	, m_GetTopic(service_id + "/" + slot_name + "/get")
	, m_SetTopic(service_id + "/" + slot_name + "/set")
	, m_ErrorTopic(service_id + "/" + slot_name + "/error")
	, m_CancelTopic(service_id + "/" + slot_name + "/cancel")
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

Uuid SlotProxy::SetAsync(const nlohmann::json &data)
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
	auto msg = m_Broker->PublishData(m_SetTopic, json_str.data(), json_str.size());
	return msg.GetTraceId();
}

Uuid SlotProxy::SetAsync(std::string_view data)
{
	if (m_ReadOnly)
	{
		throw std::runtime_error("Slot '" + m_SlotName + "' is read-only");
	}

	if (m_DataType != SlotDataType::Raw)
	{
		throw std::runtime_error("Type mismatch: slot '" + m_SlotName + "' is not a Raw slot");
	}

	auto msg = m_Broker->PublishData(m_SetTopic, data.data(), data.size());
	return msg.GetTraceId();
}

Uuid SlotProxy::SetAsync(ArrayView data)
{
	if (m_ReadOnly)
	{
		throw std::runtime_error("Slot '" + m_SlotName + "' is read-only");
	}

	if (m_DataType != SlotDataType::Array)
	{
		throw std::runtime_error("Type mismatch: slot '" + m_SlotName + "' is not an Array slot");
	}

	auto msg = m_Broker->PublishArray(m_SetTopic, data);
	return msg.GetTraceId();
}

void SlotProxy::WaitForConfirmation(MessageSubscription &subscription, const Uuid &trace_id, double timeout_seconds)
{
	Timer timer;

	while (true)
	{
		auto elapsed = timer.GetTime();
		if (elapsed >= timeout_seconds)
		{
			throw SlotTimeoutError("Timeout waiting for slot '" + m_SlotName + "' confirmation");
		}

		auto remaining = timeout_seconds - elapsed;
		if (remaining <= 0)
		{
			throw SlotTimeoutError("Timeout waiting for slot '" + m_SlotName + "' confirmation");
		}

		// Wait for next message with remaining timeout
		auto response_msg = subscription.GetNextMessage(remaining);

		// Check if this is for our trace_id
		if (response_msg->GetTraceId() == trace_id)
		{
			// Check topic to determine message type
			auto topic = response_msg->GetTopic();
			if (topic == m_GetTopic)
			{
				// Success - confirmation received
				return;
			}
			else if (topic == m_ErrorTopic)
			{
				// Error - parse error message
				auto payload = response_msg->GetPayload();
				std::string error_msg(static_cast<const char*>(payload.data), payload.info.GetSizeInBytes());
				throw SlotSetterError("Slot '" + m_SlotName + "' setter error: " + error_msg);
			}
			else if (topic == m_CancelTopic)
			{
				// Cancelled
				throw SlotCancelledError("Slot '" + m_SlotName + "' operation was cancelled");
			}
		}
		// If trace_id doesn't match, continue waiting
	}
}

void SlotProxy::Set(const nlohmann::json &data, double timeout_seconds)
{
	if (m_ReadOnly)
	{
		throw std::runtime_error("Slot '" + m_SlotName + "' is read-only");
	}

	if (m_DataType != SlotDataType::Json)
	{
		throw std::runtime_error("Type mismatch: slot '" + m_SlotName + "' is not a Json slot");
	}

	// Create subscription before publishing to avoid race condition
	auto sub = m_Broker->Subscribe(m_BaseTopic, MessageSubscriptionMode::Sequential);

	// Publish and get trace_id
	auto json_str = data.dump();
	auto msg = m_Broker->PublishData(m_SetTopic, json_str.data(), json_str.size());
	Uuid trace_id = msg.GetTraceId();

	// Wait for confirmation
	WaitForConfirmation(sub, trace_id, timeout_seconds);
}

void SlotProxy::Set(std::string_view data, double timeout_seconds)
{
	if (m_ReadOnly)
	{
		throw std::runtime_error("Slot '" + m_SlotName + "' is read-only");
	}

	if (m_DataType != SlotDataType::Raw)
	{
		throw std::runtime_error("Type mismatch: slot '" + m_SlotName + "' is not a Raw slot");
	}

	// Create subscription before publishing to avoid race condition
	auto sub = m_Broker->Subscribe(m_BaseTopic, MessageSubscriptionMode::Sequential);

	// Publish and get trace_id
	auto msg = m_Broker->PublishData(m_SetTopic, data.data(), data.size());
	Uuid trace_id = msg.GetTraceId();

	// Wait for confirmation
	WaitForConfirmation(sub, trace_id, timeout_seconds);
}

void SlotProxy::Set(ArrayView data, double timeout_seconds)
{
	if (m_ReadOnly)
	{
		throw std::runtime_error("Slot '" + m_SlotName + "' is read-only");
	}

	if (m_DataType != SlotDataType::Array)
	{
		throw std::runtime_error("Type mismatch: slot '" + m_SlotName + "' is not an Array slot");
	}

	// Create subscription before publishing to avoid race condition
	auto sub = m_Broker->Subscribe(m_BaseTopic, MessageSubscriptionMode::Sequential);

	// Publish and get trace_id
	auto msg = m_Broker->PublishArray(m_SetTopic, data);
	Uuid trace_id = msg.GetTraceId();

	// Wait for confirmation
	WaitForConfirmation(sub, trace_id, timeout_seconds);
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
