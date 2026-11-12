#ifndef SLOT_H
#define SLOT_H

#include "MessageBroker.h"
#include "Types.h"
#include "ArrayView.h"
#include "Uuid.h"

#include <nlohmann/json.hpp>

#include <functional>
#include <memory>
#include <string>
#include <thread>
#include <atomic>
#include <cstdint>

// Forward declaration
class SlotContext;

// Type-specific setter functions using SlotContext
using SlotSetterJsonFunc = std::function<void(const nlohmann::json &, SlotContext &)>;
using SlotSetterRawFunc = std::function<void(std::string_view, SlotContext &)>;
using SlotSetterArrayFunc = std::function<void(ArrayView, SlotContext &)>;

/**
 * SlotContext - Context provided to slot setters for publishing and cancellation.
 *
 * Provides:
 * - Publishing to /get topic with trace ID preservation
 * - Cancellation checking via /cancel topic subscription
 * - Broker access for advanced operations
 */
class SlotContext
{
public:
	/**
	 * Create a slot context.
	 *
	 * @param broker The message broker
	 * @param service_id The parent service ID
	 * @param slot_name The slot name
	 * @param trace_id The trace ID from the incoming /set message
	 * @param cancel_sub The subscription to /cancel topic (copy of monitor's subscription)
	 */
	SlotContext(std::shared_ptr<MessageBroker> broker,
				const std::string &service_id,
				const std::string &slot_name,
				const Uuid &trace_id,
				MessageSubscription cancel_sub);

	/**
	 * Check if this operation has been cancelled.
	 * Polls the /cancel topic for messages matching this operation's trace ID.
	 *
	 * @return true if a /cancel message was received for this trace ID
	 */
	bool IsCancelled();

	/**
	 * Publish a value to the slot's /get topic.
	 * Uses the same trace ID as the incoming /set message.
	 *
	 * @param data The JSON data to publish
	 * @return The published message
	 */
	Message Publish(const nlohmann::json &data);

	/**
	 * Publish raw data to the slot's /get topic.
	 *
	 * @param data The raw data to publish
	 * @return The published message
	 */
	Message Publish(std::string_view data);

	/**
	 * Publish array data to the slot's /get topic.
	 *
	 * @param data The array data to publish
	 * @return The published message
	 */
	Message Publish(ArrayView data);

	/**
	 * Get the message broker for advanced operations.
	 */
	std::shared_ptr<MessageBroker> GetBroker() const { return m_Broker; }

	/**
	 * Get the trace ID for this operation.
	 */
	const Uuid &GetTraceId() const { return m_TraceId; }

private:
	std::shared_ptr<MessageBroker> m_Broker;
	std::string m_ServiceId;
	std::string m_SlotName;
	Uuid m_TraceId;
	std::string m_GetTopic;
	MessageSubscription m_CancelSub;
};

/**
 * Slot - A typed communication channel between services.
 *
 * Supports:
 * - Publishing data (service -> proxy)
 * - Setting value with callback (proxy -> service -> callback)
 * - Subscribing to stream (proxy <- service continuous)
 */
class Slot
{
public:
	/**
	 * Create a new read-only slot.
	 *
	 * @param service_id The parent service ID
	 * @param broker The message broker
	 * @param name The slot name (must be unique within service)
	 * @param data_type The data type (locked at creation)
	 */
	Slot(const std::string &service_id, std::shared_ptr<MessageBroker> broker, const std::string &name, SlotDataType data_type);

	/**
	 * Create a new read-write slot with setter callback.
	 *
	 * @param service_id The parent service ID
	 * @param broker The message broker
	 * @param name The slot name (must be unique within service)
	 * @param data_type The data type (locked at creation)
	 * @param setter The callback function to call when value is set
	 */
	Slot(const std::string &service_id, std::shared_ptr<MessageBroker> broker, const std::string &name, SlotDataType data_type, SlotSetterJsonFunc setter);
	Slot(const std::string &service_id, std::shared_ptr<MessageBroker> broker, const std::string &name, SlotDataType data_type, SlotSetterRawFunc setter);
	Slot(const std::string &service_id, std::shared_ptr<MessageBroker> broker, const std::string &name, SlotDataType data_type, SlotSetterArrayFunc setter);

	/**
	 * Destructor. Cleans up the set monitor thread.
	 */
	~Slot();

	// Delete copy/move to ensure unique ownership
	Slot(const Slot &) = delete;
	Slot &operator=(const Slot &) = delete;
	Slot(Slot &&) = delete;
	Slot &operator=(Slot &&) = delete;

	/**
	 * Publish data to the slot.
	 * Broadcasts to all subscribers on /get topic.
	 * Type is validated against slot's data_type.
	 *
	 * @param data The data to publish
	 * @return The published message
	 * @throws std::runtime_error if type doesn't match slot data_type
	 */
	Message Publish(const nlohmann::json &data);
	Message Publish(std::string_view data);
	Message Publish(ArrayView data);

	/**
	 * Check if slot is read-only.
	 */
	bool IsReadOnly() const;

	/**
	 * Get the slot data type.
	 */
	SlotDataType GetDataType() const;

	/**
	 * Get the slot name.
	 */
	const std::string &GetName() const;

	/**
	 * Start the slot monitoring.
	 * Called by Service before Main().
	 */
	void Start();

	/**
	 * Stop the slot monitoring.
	 * Called by Service after Main().
	 */
	void Stop();

private:
	// Topic helpers
	std::string GetGetTopic() const { return m_ServiceId + "/" + m_Name + "/get"; }
	std::string GetSetTopic() const { return m_ServiceId + "/" + m_Name + "/set"; }
	std::string GetCancelTopic() const { return m_ServiceId + "/" + m_Name + "/cancel"; }
	std::string GetErrorTopic() const { return m_ServiceId + "/" + m_Name + "/error"; }

	// Implementation details
	std::string m_ServiceId;
	std::shared_ptr<MessageBroker> m_Broker;
	std::string m_Name;
	SlotDataType m_DataType;
	bool m_IsReadOnly;

	// Setter callback (only valid if not read-only)
	std::function<void(const nlohmann::json &, SlotContext &)> m_SetterJson;
	std::function<void(std::string_view, SlotContext &)> m_SetterRaw;
	std::function<void(ArrayView, SlotContext &)> m_SetterArray;

	// Set monitoring thread
	std::unique_ptr<std::thread> m_SetMonitorThread;
	std::atomic<bool> m_ShouldStop{false};

	// Helper to validate type
	void CheckType(SlotDataType type) const;

	// Monitor set messages
	void MonitorSetMessages();
};

#endif // SLOT_H
