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


# Fixtures for local message broker setup
@pytest.fixture(scope='module')
def header_memory():
    """Create memory for message broker header."""
    header = LocalMemory.create(1024 * 1024 * 512)
    yield header


@pytest.fixture(scope='module')
def local_broker(header_memory):
    """Create a local message broker for testing."""
    block = LocalMemory.create(1024 * 1024 * 1024)
    broker = LocalMessageBroker.create(header_memory, [block])
    yield broker


@pytest.fixture
def unused_port():
    """Generate unique port numbers for tests."""
    port = 15000
    
    def get_port():
        nonlocal port
        port += 1
        return port
    
    return get_port


class TestTopicRouting:
    """Test topic routing logic (local vs remote)."""
    
    def test_local_topic_detection(self, local_broker, unused_port):
        """Test that local topics are correctly identified."""
        port = unused_port()
        
        # Create remote broker with local machine name
        peers = []
        remote_broker = RemoteMessageBroker(local_broker, "machine1", peers)
        
        # Publish to local topic
        local_topic = "machine1/test_local"
        data = b'local data'
        remote_broker.publish_data(local_topic, data)
        
        # Verify message is in local broker
        msg = local_broker.get_current_message(local_topic)
        assert msg is not None
        assert msg.payload.data == data
    
    def test_remote_topic_routing(self, local_broker, unused_port):
        """Test that remote topics trigger network requests."""
        port = unused_port()
        
        # Create server and client setup
        peers = [PeerConfig("machine2", "127.0.0.1", port)]
        remote_broker = RemoteMessageBroker(local_broker, "machine1", peers)
        
        # Create server for machine2
        server_broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024 * 10)]
        )
        server = RemoteBrokerServer(server_broker, port)
        server.start()
        
        try:
            # Publish to remote topic
            remote_topic = "machine2/test_remote"
            data = b'remote data'
            remote_broker.publish_data(remote_topic, data)
            
            # Verify message arrived at server broker
            time.sleep(0.1)  # Allow network transmission
            msg = server_broker.get_current_message(remote_topic)
            assert msg is not None
            assert msg.payload.data == data
        finally:
            server.stop()


class TestSerialization:
    """Test message serialization and deserialization."""
    
    def test_message_round_trip(self, local_broker, unused_port):
        """Test that messages can be serialized and deserialized correctly."""
        port = unused_port()
        
        # Setup server
        server_broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024 * 10)]
        )
        server = RemoteBrokerServer(server_broker, port)
        server.start()
        
        try:
            # Setup client
            peers = [PeerConfig("server", "127.0.0.1", port)]
            client_broker = RemoteMessageBroker(local_broker, "client", peers)
            
            # Publish array with metadata
            topic = "server/test_roundtrip"
            arr = np.array([1, 2, 3, 4, 5], dtype='float64')
            
            msg = client_broker.prepare_message(topic, arr.nbytes)
            msg.payload = arr
            msg.metadata['test_key'] = 42
            client_broker.publish_message(msg)
            
            # Verify at server
            time.sleep(0.1)
            received = server_broker.get_current_message(topic)
            assert received is not None
            assert np.array_equal(received.payload, arr)
        finally:
            server.stop()
    
    def test_different_dtypes(self, local_broker, unused_port):
        """Test serialization with various data types."""
        port = unused_port()
        
        server_broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024 * 10)]
        )
        server = RemoteBrokerServer(server_broker, port)
        server.start()
        
        try:
            peers = [PeerConfig("server", "127.0.0.1", port)]
            client_broker = RemoteMessageBroker(local_broker, "client", peers)
            
            dtypes = ['int8', 'uint8', 'int32', 'float32', 'float64']
            for dtype in dtypes:
                topic = f"server/test_{dtype}"
                arr = np.array([1, 2, 3], dtype=dtype)
                
                client_broker.publish_array(topic, arr)
                time.sleep(0.05)
                
                received = server_broker.get_current_message(topic)
                assert received is not None
                assert received.payload.dtype == dtype
                assert np.array_equal(received.payload, arr)
        finally:
            server.stop()
    
    def test_multidimensional_arrays(self, local_broker, unused_port):
        """Test serialization of multidimensional arrays."""
        port = unused_port()
        
        server_broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024 * 10)]
        )
        server = RemoteBrokerServer(server_broker, port)
        server.start()
        
        try:
            peers = [PeerConfig("server", "127.0.0.1", port)]
            client_broker = RemoteMessageBroker(local_broker, "client", peers)
            
            shapes = [[10, 10], [5, 5, 5], [3, 3, 3, 3]]
            for shape in shapes:
                topic = f"server/test_shape_{len(shape)}d"
                arr = np.random.randn(*shape).astype('float32')
                
                client_broker.publish_array(topic, arr)
                time.sleep(0.05)
                
                received = server_broker.get_current_message(topic)
                assert received is not None
                assert np.array_equal(received.payload, arr)
                assert list(received.payload.shape) == list(arr.shape)
        finally:
            server.stop()


class TestRemoteBrokerServer:
    """Test RemoteBrokerServer functionality."""
    
    def test_server_start_stop(self, unused_port):
        """Test that server can start and stop correctly."""
        port = unused_port()
        
        broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024)]
        )
        
        server = RemoteBrokerServer(broker, port)
        assert not server.is_running
        
        server.start()
        assert server.is_running
        
        server.stop()
        assert not server.is_running
    
    def test_request_handlers(self, local_broker, unused_port):
        """Test that all request handlers work correctly."""
        port = unused_port()
        
        server_broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024 * 10)]
        )
        server = RemoteBrokerServer(server_broker, port, num_workers=2)
        server.start()
        
        try:
            peers = [PeerConfig("server", "127.0.0.1", port)]
            client_broker = RemoteMessageBroker(local_broker, "client", peers)
            
            topic = "server/test_handlers"
            
            # Test PUBLISH
            data = b'test data'
            client_broker.publish_data(topic, data)
            time.sleep(0.1)
            
            # Test GET_CURRENT
            msg = client_broker.get_current_message(topic)
            assert msg is not None
            
            # Test GET_RATE
            rate = client_broker.get_message_rate(topic)
            assert rate >= 0.0
            
            # Test LIST_TOPICS (returned as comma-separated string)
            topics = server_broker.get_all_message_topics()
            assert topic in topics
        finally:
            server.stop()


class TestConcurrency:
    """Test concurrent access and thread safety."""
    
    def test_concurrent_publishes(self, local_broker, unused_port):
        """Test concurrent publishing from multiple threads."""
        port = unused_port()
        
        server_broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024 * 100)]
        )
        server = RemoteBrokerServer(server_broker, port, num_workers=4)
        server.start()
        
        try:
            peers = [PeerConfig("server", "127.0.0.1", port)]
            client_broker = RemoteMessageBroker(local_broker, "client", peers)
            
            num_messages = 50
            errors = []
            
            def publish_messages(thread_id):
                try:
                    for i in range(num_messages):
                        topic = f"server/thread_{thread_id}/msg_{i}"
                        data = f"data from thread {thread_id}, msg {i}".encode()
                        client_broker.publish_data(topic, data)
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
            time.sleep(0.2)
            topics = server_broker.get_all_message_topics()
            assert len(topics) >= num_messages
        finally:
            server.stop()
    
    def test_server_thread_pool(self, local_broker, unused_port):
        """Test that server thread pool handles concurrent requests."""
        port = unused_port()
        
        server_broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024 * 10)]
        )
        # Use multiple workers
        server = RemoteBrokerServer(server_broker, port, num_workers=4)
        server.start()
        
        try:
            peers = [PeerConfig("server", "127.0.0.1", port)]
            client_broker = RemoteMessageBroker(local_broker, "client", peers)
            
            # Publish multiple messages
            for i in range(10):
                topic = f"server/concurrent_{i}"
                client_broker.publish_data(topic, f"msg {i}".encode())
            
            time.sleep(0.1)
            
            # All messages should be available
            for i in range(10):
                topic = f"server/concurrent_{i}"
                msg = server_broker.get_current_message(topic)
                assert msg is not None
        finally:
            server.stop()


class TestTimeoutHandling:
    """Test timeout handling in GetNextMessage."""
    
    def test_get_next_timeout(self, local_broker, unused_port):
        """Test that GetNextMessage respects timeout."""
        port = unused_port()
        
        server_broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024 * 10)]
        )
        server = RemoteBrokerServer(server_broker, port)
        server.start()
        
        try:
            peers = [PeerConfig("server", "127.0.0.1", port)]
            client_broker = RemoteMessageBroker(local_broker, "client", peers)
            
            # Try to get message from non-existent topic with short timeout
            topic = "server/non_existent"
            start_time = time.time()
            
            msg = client_broker.get_next_message(topic, timeout_in_seconds=0.1)
            elapsed = time.time() - start_time
            
            # Should return None on timeout
            assert msg is None
            # Should complete within reasonable time (allowing for network overhead)
            assert elapsed < 0.5
        finally:
            server.stop()
    
    def test_get_next_with_data(self, local_broker, unused_port):
        """Test GetNextMessage returns data when available."""
        port = unused_port()
        
        server_broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024 * 10)]
        )
        server = RemoteBrokerServer(server_broker, port)
        server.start()
        
        try:
            peers = [PeerConfig("server", "127.0.0.1", port)]
            client_broker = RemoteMessageBroker(local_broker, "client", peers)
            
            topic = "server/test_get_next"
            data = b'test data'
            
            # Publish first
            client_broker.publish_data(topic, data)
            time.sleep(0.1)
            
            # Now get next message
            msg = client_broker.get_next_message(topic, timeout_in_seconds=1.0)
            assert msg is not None
            assert msg.payload.data == data
        finally:
            server.stop()


class TestSubscriptionModes:
    """Test different subscription modes."""
    
    def test_newest_only_subscription(self, local_broker, unused_port):
        """Test NewestOnly subscription mode over network."""
        port = unused_port()
        
        server_broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024 * 10)]
        )
        server = RemoteBrokerServer(server_broker, port)
        server.start()
        
        try:
            peers = [PeerConfig("server", "127.0.0.1", port)]
            client_broker = RemoteMessageBroker(local_broker, "client", peers)
            
            topic = "server/test_newest"
            
            # Publish multiple messages
            for i in range(5):
                client_broker.publish_data(topic, f"msg {i}".encode())
                time.sleep(0.01)
            
            # Subscribe with NewestOnly
            sub = client_broker.subscribe(topic, mode=MessageSubscriptionMode.NewestOnly)
            
            # Should get the newest message (msg 4)
            msg = sub.get_next_message(timeout_in_seconds=1.0)
            assert msg is not None
            assert b'4' in msg.payload.data
        finally:
            server.stop()
    
    def test_sequential_subscription(self, local_broker, unused_port):
        """Test Sequential subscription mode over network."""
        port = unused_port()
        
        server_broker = LocalMessageBroker.create(
            LocalMemory.create(1024 * 1024),
            [LocalMemory.create(1024 * 1024 * 10)]
        )
        server = RemoteBrokerServer(server_broker, port)
        server.start()
        
        try:
            peers = [PeerConfig("server", "127.0.0.1", port)]
            client_broker = RemoteMessageBroker(local_broker, "client", peers)
            
            topic = "server/test_sequential"
            
            # Publish multiple messages
            for i in range(5):
                client_broker.publish_data(topic, f"msg {i}".encode())
                time.sleep(0.01)
            
            # Subscribe with Sequential
            sub = client_broker.subscribe(topic, mode=MessageSubscriptionMode.Sequential)
            
            # Should get messages in order
            for i in range(5):
                msg = sub.get_next_message(timeout_in_seconds=1.0)
                assert msg is not None
                assert str(i).encode() in msg.payload.data
        finally:
            server.stop()


class TestErrorHandling:
    """Test error handling."""
    
    def test_unknown_peer(self, local_broker):
        """Test that accessing unknown peer raises error."""
        peers = []  # No peers configured
        remote_broker = RemoteMessageBroker(local_broker, "machine1", peers)
        
        # Trying to access remote topic should raise error
        with pytest.raises(RuntimeError, match="Unknown peer"):
            remote_broker.publish_data("unknown_machine/topic", b'data')
    
    def test_server_not_running(self, local_broker, unused_port):
        """Test behavior when server is not running."""
        port = unused_port()
        
        # Don't start server
        peers = [PeerConfig("server", "127.0.0.1", port)]
        remote_broker = RemoteMessageBroker(local_broker, "client", peers)
        
        # Publish should fail or timeout
        with pytest.raises(RuntimeError):
            remote_broker.publish_data("server/topic", b'data')
