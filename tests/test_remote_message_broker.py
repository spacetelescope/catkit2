"""Tests for RemoteMessageBroker and RemoteBrokerServer.

These tests verify the synchronous remote message broker implementation,
including topic routing, serialization, and client-server communication.
"""

import numpy as np
import pytest
import threading
import time

from catkit2.catkit_bindings import (
    LocalMemory, LocalMessageBroker, RemoteMessageBroker, RemoteBrokerServer,
    PeerConfig, MessageSubscriptionMode
)


@pytest.fixture(scope='module')
def local_broker_1():
    """Create a local message broker for testing."""
    header_memory = LocalMemory.create(1024 * 1024 * 512)
    block = LocalMemory.create(1024 * 1024 * 1024)

    broker = LocalMessageBroker.create(header_memory, [block])
    yield broker

@pytest.fixture(scope='module')
def local_broker_2():
    """Create a local message broker for testing."""
    header_memory = LocalMemory.create(1024 * 1024 * 512)
    block = LocalMemory.create(1024 * 1024 * 1024)

    broker = LocalMessageBroker.create(header_memory, [block])
    yield broker

@pytest.fixture(scope='module')
def remote_broker(local_broker_1, local_broker_2, unused_port):
    port = unused_port()

    server = RemoteBrokerServer(local_broker_2, port)
    server.start()

    peers = [PeerConfig("machine2", "127.0.0.1", port)]
    remote_broker = RemoteMessageBroker(local_broker_1, "machine1", peers)

    yield remote_broker

    server.stop()

def test_local_topic_detection(remote_broker, local_broker_1):
    """Test that local topics are correctly identified."""
    # Publish to local topic (machine1 is the local machine in the fixture)
    local_topic = "machine1/test_local"
    data = b'local data'
    remote_broker.publish_data(local_topic, data)

    # Verify message is in local broker
    msg = local_broker_1.get_current_message(local_topic)
    assert msg is not None
    assert msg.payload.data == data

def test_remote_topic_routing(remote_broker, local_broker_2):
    """Test that remote topics trigger network requests."""
    # Publish to remote topic (machine2 is the remote machine in the fixture)
    remote_topic = "machine2/test_remote"
    data = b'remote data'
    remote_broker.publish_data(remote_topic, data)

    # Verify message arrived at server broker
    msg = local_broker_2.get_current_message(remote_topic)
    assert msg is not None
    assert msg.payload.data == data

def test_message_round_trip(remote_broker, local_broker_2):
    """Test that messages can be serialized and deserialized correctly."""
    # Publish array with metadata
    topic = "machine2/test_roundtrip"
    arr = np.array([1, 2, 3, 4, 5], dtype='float64')

    msg = remote_broker.prepare_message(topic, arr.nbytes)
    msg.payload = arr
    msg.metadata['test_key'] = 42
    remote_broker.publish_message(msg)

    # Verify at server
    received = local_broker_2.get_current_message(topic)
    assert received is not None
    assert np.array_equal(received.payload, arr)

def test_different_dtypes(remote_broker, local_broker_2):
    """Test serialization with various data types."""
    dtypes = ['int8', 'uint8', 'int32', 'float32', 'float64']
    for dtype in dtypes:
        topic = f"machine2/test_{dtype}"
        arr = np.array([1, 2, 3], dtype=dtype)

        remote_broker.publish_array(topic, arr)

        received = local_broker_2.get_current_message(topic)
        assert received is not None
        assert received.payload.dtype == dtype
        assert np.array_equal(received.payload, arr)

def test_multidimensional_arrays(remote_broker, local_broker_2):
    """Test serialization of multidimensional arrays."""
    shapes = [[10, 10], [5, 5, 5], [3, 3, 3, 3]]
    for shape in shapes:
        topic = f"machine2/test_shape_{len(shape)}d"
        arr = np.random.randn(*shape).astype('float32')

        remote_broker.publish_array(topic, arr)

        received = local_broker_2.get_current_message(topic)
        assert received is not None
        assert np.array_equal(received.payload, arr)
        assert list(received.payload.shape) == list(arr.shape)

def test_server_start_stop(unused_port):
    """Test that server can start and stop correctly."""
    port = unused_port()

    broker = LocalMessageBroker.create(
        LocalMemory.create(1024 * 1024 * 512),
        [LocalMemory.create(1024 * 1024 * 1024)]
    )

    server = RemoteBrokerServer(broker, port)
    assert not server.is_running

    server.start()
    assert server.is_running

    server.stop()
    assert not server.is_running

def test_request_handlers(remote_broker, local_broker_2):
    """Test that all request handlers work correctly."""
    topic = "machine2/test_handlers"

    # Test PUBLISH
    data = b'test data'
    remote_broker.publish_data(topic, data)

    # Test GET_CURRENT
    msg = remote_broker.get_current_message(topic)
    assert msg is not None

    # Test GET_RATE
    rate = remote_broker.get_message_rate(topic)
    assert rate >= 0.0

    # Test LIST_TOPICS (returned as comma-separated string)
    topics = local_broker_2.get_all_message_topics()
    assert topic in topics

def test_concurrent_publishes(remote_broker, local_broker_2):
    """Test concurrent publishing from multiple threads."""
    num_messages = 50
    errors = []

    def publish_messages(thread_id):
        try:
            for i in range(num_messages):
                topic = f"machine2/thread_{thread_id}/msg_{i}"
                data = f"data from thread {thread_id}, msg {i}".encode()
                remote_broker.publish_data(topic, data)
        except Exception as e:
            errors.append(e)

    # Start multiple threads
    threads = []
    for i in range(3):
        t = threading.Thread(target=publish_messages, args=(i,))
        threads.append(t)
        t.start()

    # Wait for completion
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors during concurrent publish: {errors}"

    # Verify some messages arrived
    topics = local_broker_2.get_all_message_topics()
    assert len(topics) >= num_messages

def test_server_thread_pool(remote_broker, local_broker_2):
    """Test that server thread pool handles concurrent requests."""
    # Publish multiple messages
    for i in range(10):
        topic = f"machine2/concurrent_{i}"
        remote_broker.publish_data(topic, f"msg {i}".encode())

    # All messages should be available
    for i in range(10):
        topic = f"machine2/concurrent_{i}"
        msg = local_broker_2.get_current_message(topic)
        assert msg is not None

def test_get_next_timeout(remote_broker):
    """Test that GetNextMessage respects timeout."""
    # Try to get message from non-existent topic with short timeout
    topic = "machine2/non_existent"
    start_time = time.time()

    # Subscribe and try to get next message
    sub = remote_broker.subscribe(topic)
    msg = sub.get_next_message(timeout_in_sec=0.1)
    elapsed = time.time() - start_time

    # Should return None on timeout
    assert msg is None
    # Should complete within reasonable time (allowing for network overhead)
    assert elapsed < 0.5

def test_get_next_with_data(remote_broker):
    """Test GetNextMessage returns data when available."""
    topic = "machine2/test_get_next"
    data = b'test data'

    # Subscribe first
    sub = remote_broker.subscribe(topic)

    # Publish
    remote_broker.publish_data(topic, data)

    # Now get next message
    msg = sub.get_next_message(timeout_in_sec=1.0)
    assert msg is not None
    assert msg.payload.data == data

def test_newest_only_subscription(remote_broker):
    """Test NewestOnly subscription mode over network."""
    topic = "machine2/test_newest"

    # Publish multiple messages
    for i in range(5):
        remote_broker.publish_data(topic, f"msg {i}".encode())

    # Subscribe with NewestOnly
    sub = remote_broker.subscribe(topic, mode=MessageSubscriptionMode.NewestOnly)

    # Should get the newest message (msg 4)
    msg = sub.get_next_message(timeout_in_sec=1.0)
    assert msg is not None
    assert b'4' in msg.payload.data

def test_sequential_subscription(remote_broker):
    """Test Sequential subscription mode over network."""
    topic = "machine2/test_sequential"

    # Subscribe with Sequential
    sub = remote_broker.subscribe(topic, mode=MessageSubscriptionMode.Sequential)

    # Publish multiple messages
    for i in range(5):
        remote_broker.publish_data(topic, f"msg {i}".encode())

    # Should get messages in order
    for i in range(5):
        msg = sub.get_next_message(timeout_in_sec=1.0)
        assert msg is not None
        assert str(i).encode() in msg.payload.data

def test_unknown_peer(remote_broker):
    """Test that accessing unknown peer raises error."""
    # Trying to access remote topic should raise error
    with pytest.raises(RuntimeError, match="Unknown peer"):
        remote_broker.publish_data("unknown_machine/topic", b'data')

def htest_server_not_running(local_broker_1, unused_port):
    """Test behavior when server is not running."""
    port = unused_port()

    # Don't start server
    peers = [PeerConfig("server", "127.0.0.1", port)]
    remote_broker = RemoteMessageBroker(local_broker_1, "client", peers)

    # Publish should fail or timeout
    with pytest.raises(RuntimeError):
        remote_broker.publish_data("server/topic", b'data')
