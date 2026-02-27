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
	 * Set the slot value.
	 * Publishes to /set topic, triggers service setter callback.
	 * Type is validated against slot's data_type.
	 *
	 * @param data The data to set
	 * @throws std::runtime_error if slot is read-only or type mismatch
	 */
	void Set(const nlohmann::json &data);
	void Set(std::string_view data);
	void Set(ArrayView data);

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
	std::shared_ptr<MessageBroker> m_Broker;
	std::string m_ServiceId;
	std::string m_SlotName;
	bool m_ReadOnly;
	SlotDataType m_DataType;
	std::string m_GetTopic;
	std::string m_SetTopic;
};

#endif // SLOT_PROXY_H
