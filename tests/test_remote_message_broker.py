import numpy as np

from catkit2 import catkit_bindings as cb


def test_unified_message_broker_client_to_server():
    """
    Test message broker can publish and subscribe within same broker instance.
    """
    # Create memory for the broker
    header_memory = cb.LocalMemory.create(512 * 1024 * 1024)
    block = cb.LocalMemory.create(1024 * 1024 * 1024)
    
    # Create a single broker instance
    broker = cb.LocalMessageBroker.create(header_memory, [block])

    topic = "unified_broker/test"
    payload = np.arange(32, dtype=np.uint16)

    # Publish a message
    broker.publish_array(topic, payload)

    # Subscribe and receive the message
    subscription = broker.subscribe(
        topic, mode=cb.MessageSubscriptionMode.Sequential
    )
    
    try:
        message = subscription.get_next_message(0.5)
    except RuntimeError:
        message = None

    assert message is not None, (
        "Failed to receive message from broker"
    )
    np.testing.assert_array_equal(message.payload, payload)


def test_unified_message_broker_server_to_client():
    """
    Test message broker with multiple subscriptions to same topic.
    """
    # Create memory for the broker
    header_memory = cb.LocalMemory.create(512 * 1024 * 1024)
    block = cb.LocalMemory.create(1024 * 1024 * 1024)
    
    # Create a single broker instance
    broker = cb.LocalMessageBroker.create(header_memory, [block])

    topic = "unified_broker/multi_sub"
    payload = np.linspace(0.0, 1.0, 16, dtype=np.float32)

    # Create first subscription before publishing
    subscription1 = broker.subscribe(
        topic, mode=cb.MessageSubscriptionMode.Sequential
    )
    
    # Publish message
    broker.publish_array(topic, payload)
    
    # Create second subscription after publishing (should get newest)
    subscription2 = broker.subscribe(
        topic, mode=cb.MessageSubscriptionMode.NewestOnly
    )

    # First subscription should get the message
    try:
        message1 = subscription1.get_next_message(0.5)
    except RuntimeError:
        message1 = None
    
    assert message1 is not None, (
        "First subscription failed to receive message"
    )
    np.testing.assert_allclose(message1.payload, payload)
    
    # Second subscription should also get the message
    try:
        message2 = subscription2.get_next_message(0.5)
    except RuntimeError:
        message2 = None

    assert message2 is not None, (
        "Second subscription failed to receive message"
    )
    np.testing.assert_allclose(message2.payload, payload)
