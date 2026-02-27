#ifndef SLOT_PROXY_H
#define SLOT_PROXY_H

#include "MessageBroker.h"
#include "Types.h"
#include "ArrayView.h"

#include <nlohmann/json.hpp>

#include <string>
#include <memory>
#include <cstdint>

class TestbedProxy;

/**
 * SlotProxy - Client-side proxy for accessing a remote Slot.
 *
 * Provides:
 * - Getting latest value from /get topic (with type validation)
 * - Setting value via /set topic (with type validation)
 * - Subscribing to /get topic for streaming
 */
class SlotProxy
{
public:
	/**
	 * Create a new slot proxy.
	 *
	 * @param broker The message broker
	 * @param service_id The service ID
	 * @param slot_name The slot name
	 * @param read_only Whether the slot is read-only
	 * @param data_type The slot data type for validation
	 */
	SlotProxy(std::shared_ptr<MessageBroker> broker, const std::string &service_id, const std::string &slot_name, bool read_only, SlotDataType data_type);

	/**
	 * Get the latest value from the slot.
	 *
	 * @return The latest published data
	 * @throws std::runtime_error on timeout or error
	 */
	nlohmann::json GetJson() const;
	std::string_view GetRaw() const;
	ArrayView GetArray() const;

	/**
	 * Set the slot value asynchronously.
	 * Publishes to /set topic, triggers service setter callback.
	 * Type is validated against slot's data_type.
	 *
	 * @param data The data to set
	 * @return The trace ID for tracking the operation
	 * @throws std::runtime_error if slot is read-only or type mismatch
	 */
	Uuid SetAsync(const nlohmann::json &data);
	Uuid SetAsync(std::string_view data);
	Uuid SetAsync(ArrayView data);

	/**
	 * Set the slot value synchronously with confirmation.
	 * Publishes to /set topic and waits for confirmation on /get or error on /error.
	 *
	 * @param data The data to set
	 * @param timeout_seconds Maximum time to wait for confirmation (default 5.0)
	 * @throws std::runtime_error if slot is read-only, type mismatch, timeout, or setter error
	 * @throws SlotTimeoutError if confirmation not received within timeout
	 * @throws SlotSetterError if service setter throws exception
	 * @throws SlotCancelledError if operation was cancelled
	 */
	void Set(const nlohmann::json &data, double timeout_seconds = 5.0);
	void Set(std::string_view data, double timeout_seconds = 5.0);
	void Set(ArrayView data, double timeout_seconds = 5.0);

	/**
	 * Subscribe to slot updates.
	 *
	 * @param mode Subscription mode (NewestOnly or Sequential)
	 * @return MessageSubscription for receiving updates
	 */
	MessageSubscription Subscribe(MessageSubscriptionMode mode = MessageSubscriptionMode::NewestOnly);

	/**
	 * Check if slot is read-only.
	 */
	bool IsReadOnly() const;

	/**
	 * Get the slot name.
	 */
	const std::string &GetSlotName() const;

	/**
	 * Get the slot data type.
	 */
	SlotDataType GetDataType() const;

private:
	/**
	 * Wait for confirmation message with matching trace_id.
	 *
	 * @param subscription The subscription to wait on
	 * @param trace_id The trace ID to match
	 * @param timeout_seconds Maximum time to wait
	 * @throws SlotTimeoutError if timeout expires
	 * @throws SlotSetterError if error message received
	 * @throws SlotCancelledError if cancel message received
	 */
	void WaitForConfirmation(MessageSubscription &subscription, const Uuid &trace_id, double timeout_seconds);
	std::shared_ptr<MessageBroker> m_Broker;
	std::string m_ServiceId;
	std::string m_SlotName;
	bool m_ReadOnly;
	SlotDataType m_DataType;
	std::string m_BaseTopic;
	std::string m_GetTopic;
	std::string m_SetTopic;
	std::string m_ErrorTopic;
	std::string m_CancelTopic;
};

#endif // SLOT_PROXY_H
