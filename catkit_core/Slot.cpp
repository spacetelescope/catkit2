#include "Slot.h"
#include "Log.h"

#include <stdexcept>
#include <sstream>
#include <chrono>
#include <cstring>

using namespace std::literals::string_literals;

// Read-only constructor
Slot::Slot(const std::string &service_id, std::shared_ptr<MessageBroker> broker, const std::string &name, SlotDataType data_type)
	: m_ServiceId(service_id)
	, m_Broker(broker)
	, m_Name(name)
	, m_DataType(data_type)
	, m_IsReadOnly(true)
{
}

// Read-write constructors
Slot::Slot(const std::string &service_id, std::shared_ptr<MessageBroker> broker, const std::string &name, SlotDataType data_type, SlotSetterJsonFunc setter)
	: m_ServiceId(service_id)
	, m_Broker(broker)
	, m_Name(name)
	, m_DataType(data_type)
	, m_IsReadOnly(false)
	, m_SetterJson(setter)
	, m_SetterRaw(nullptr)
	, m_SetterArray(nullptr)
{
}

Slot::Slot(const std::string &service_id, std::shared_ptr<MessageBroker> broker, const std::string &name, SlotDataType data_type, SlotSetterRawFunc setter)
	: m_ServiceId(service_id)
	, m_Broker(broker)
	, m_Name(name)
	, m_DataType(data_type)
	, m_IsReadOnly(false)
	, m_SetterJson(nullptr)
	, m_SetterRaw(setter)
	, m_SetterArray(nullptr)
{
}

Slot::Slot(const std::string &service_id, std::shared_ptr<MessageBroker> broker, const std::string &name, SlotDataType data_type, SlotSetterArrayFunc setter)
	: m_ServiceId(service_id)
	, m_Broker(broker)
	, m_Name(name)
	, m_DataType(data_type)
	, m_IsReadOnly(false)
	, m_SetterJson(nullptr)
	, m_SetterRaw(nullptr)
	, m_SetterArray(setter)
{
}

Slot::~Slot()
{
	Stop();
}

void Slot::CheckType(SlotDataType type) const
{
	if (type != m_DataType)
	{
		throw std::runtime_error("Type mismatch for slot '" + m_Name + "'");
	}
}

Message Slot::Publish(const nlohmann::json &data)
{
	CheckType(SlotDataType::Json);
	std::string json_str = data.dump();
	return m_Broker->PublishData(GetGetTopic(), json_str.data(), json_str.size());
}

Message Slot::Publish(std::string_view data)
{
	CheckType(SlotDataType::Raw);
	return m_Broker->PublishData(GetGetTopic(), data.data(), data.size());
}

Message Slot::Publish(ArrayView data)
{
	CheckType(SlotDataType::Array);
	return m_Broker->PublishArray(GetGetTopic(), data);
}

bool Slot::IsReadOnly() const
{
	return m_IsReadOnly;
}

SlotDataType Slot::GetDataType() const
{
	return m_DataType;
}

const std::string &Slot::GetName() const
{
	return m_Name;
}

void Slot::Start()
{
	if (m_IsReadOnly || m_SetMonitorThread)
		return;

	m_ShouldStop = false;
	m_SetMonitorThread = std::make_unique<std::thread>(&Slot::MonitorSetMessages, this);
}

void Slot::Stop()
{
	m_ShouldStop = true;
	if (m_SetMonitorThread && m_SetMonitorThread->joinable())
	{
		m_SetMonitorThread->join();
		m_SetMonitorThread.reset();
	}
}

void Slot::MonitorSetMessages()
{
	auto set_sub = m_Broker->Subscribe(GetSetTopic(), MessageSubscriptionMode::Sequential);

	// Subscribe to /cancel topic once - will be copied for each operation
	auto cancel_sub = m_Broker->Subscribe(GetCancelTopic(), MessageSubscriptionMode::Sequential);

	while (!m_ShouldStop)
	{
		try
		{
			auto message = set_sub.GetNextMessage(0.1);
			if (!message)
				continue;

			auto payload = message->GetPayload();
			auto payload_size = payload.info.GetSizeInBytes();
			auto trace_id = message->GetTraceId();

			// Create context with copy of cancel subscription
			SlotContext context(m_Broker, m_ServiceId, m_Name, trace_id, cancel_sub);

			try
			{
				switch (m_DataType)
				{
				case SlotDataType::Json:
				{
					if (!payload.data || payload_size == 0)
					{
						LOG_ERROR("Slot " + m_Name + ": Received empty JSON payload");
						continue;
					}

					auto data = (char *) payload.data;
					auto json_data = nlohmann::json::parse(data, data + payload_size);

					m_SetterJson(json_data, context);

					break;
				}
					case SlotDataType::Raw:
					{
						std::string_view raw_data(static_cast<const char*>(payload.data), payload_size);

						m_SetterRaw(raw_data, context);

						break;
					}
					case SlotDataType::Array:
					{
						m_SetterArray(payload, context);

						break;
					}
				}
			}
			catch (const std::exception& e)
			{
				std::string error_message = "Setter error: "s + e.what();
				LOG_ERROR("Slot " + m_Name + ": " + error_message);
				m_Broker->PublishData(GetErrorTopic(), error_message.data(), error_message.size(), trace_id);
			}
		}
		catch (const std::exception& e)
		{
			LOG_ERROR(std::string("Slot " + m_Name + ": Error in set monitor: " + e.what()));
		}
	}
}

// SlotContext implementation

SlotContext::SlotContext(std::shared_ptr<MessageBroker> broker,
						 const std::string &service_id,
						 const std::string &slot_name,
						 const Uuid &trace_id,
						 MessageSubscription cancel_sub)
	: m_Broker(broker)
	, m_ServiceId(service_id)
	, m_SlotName(slot_name)
	, m_TraceId(trace_id)
	, m_GetTopic(service_id + "/" + slot_name + "/get")
	, m_CancelSub(std::move(cancel_sub))
{
}

bool SlotContext::IsCancelled()
{
	// Poll for cancel messages
	while (auto msg = m_CancelSub.TryGetNextMessage())
	{
		auto payload = msg->GetPayload();
		if (payload.info.GetSizeInBytes() != sizeof(Uuid))
		{
			// Invalid cancel message format, skip
			continue;
		}

		// Parse trace_id from payload
		Uuid cancel_trace_id;
		std::memcpy(&cancel_trace_id, payload.data, sizeof(Uuid));

		if (cancel_trace_id == m_TraceId)
		{
			return true;
		}
	}

	return false;
}

Message SlotContext::Publish(const nlohmann::json &data)
{
	std::string json_str = data.dump();
	return m_Broker->PublishData(m_GetTopic, json_str.data(), json_str.size(), m_TraceId);
}

Message SlotContext::Publish(std::string_view data)
{
	return m_Broker->PublishData(m_GetTopic, data.data(), data.size(), m_TraceId);
}

Message SlotContext::Publish(ArrayView data)
{
	return m_Broker->PublishArray(m_GetTopic, data, m_TraceId);
}
