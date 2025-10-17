import socket
import time

import numpy as np

from catkit2 import catkit_bindings as cb


def _free_endpoint():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"tcp://127.0.0.1:{port}"


def _wait_for_message(subscription, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        message = subscription.try_get_next_message()
        if message is not None:
            return message
        time.sleep(0.05)
    return None


def test_unified_message_broker_client_to_server():
    endpoint = _free_endpoint()

    # Create server-side unified broker
    server_memory = cb.LocalMemory.create(64 * 1024 * 1024)
    server_config = {'mode': 'server', 'endpoint': endpoint}
    server_broker = cb.MessageBroker.create_unified(
        'server', [server_memory], server_config)

    # Create client-side unified broker
    client_memory = cb.LocalMemory.create(64 * 1024 * 1024)
    client_config = {'mode': 'client', 'endpoint': endpoint}
    client_broker = cb.MessageBroker.create_unified(
        'client', [client_memory], client_config)

    topic = "unified_broker/test"
    payload = np.arange(32, dtype=np.uint16)

    # Allow sockets to connect.
    time.sleep(0.2)

    client_broker.publish_array(topic, payload)

    subscription = server_broker.subscribe(
        topic, mode=cb.MessageSubscriptionMode.Sequential)
    message = _wait_for_message(subscription)

    assert message is not None, (
        "Server did not receive message from remote client")
    np.testing.assert_array_equal(message.payload, payload)

    # Clean up to avoid lingering threads.
    del client_broker
    del server_broker
    time.sleep(0.05)


def test_unified_message_broker_server_to_client():
    endpoint = _free_endpoint()

    # Create server-side unified broker
    server_memory = cb.LocalMemory.create(64 * 1024 * 1024)
    server_config = {'mode': 'server', 'endpoint': endpoint}
    server_broker = cb.MessageBroker.create_unified(
        'server', [server_memory], server_config)

    # Create client-side unified broker
    client_memory = cb.LocalMemory.create(64 * 1024 * 1024)
    client_config = {'mode': 'client', 'endpoint': endpoint}
    client_broker = cb.MessageBroker.create_unified(
        'client', [client_memory], client_config)

    topic = "unified_broker/echo"
    payload = np.linspace(0.0, 1.0, 16, dtype=np.float32)

    time.sleep(0.2)

    server_broker.publish_array(topic, payload)

    subscription = client_broker.subscribe(
        topic, mode=cb.MessageSubscriptionMode.Sequential)
    message = _wait_for_message(subscription)

    assert message is not None, "Client did not receive broadcast from server"
    np.testing.assert_allclose(message.payload, payload)

    del client_broker
    del server_broker
    time.sleep(0.05)
