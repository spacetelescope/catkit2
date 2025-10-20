import zmq
import threading
import traceback
import time
import logging
import struct
import numpy as np


def serialize_array(array, dtype=None, shape=None):
    """Serialize numpy array to bytes with metadata.

    Parameters
    ----------
    array : numpy.ndarray
        Array to serialize
    dtype : str, optional
        Force dtype (defaults to array.dtype.str)
    shape : tuple, optional
        Force shape (defaults to array.shape)

    Returns
    -------
    bytes
        Serialized data with metadata header
    """
    if dtype is None:
        dtype = str(array.dtype)
    if shape is None:
        shape = array.shape

    # Create header: dtype_len (1 byte) | dtype_str | shape_len (1 byte)
    # | shape_data (2 bytes per dimension for values up to 65535)
    dtype_bytes = dtype.encode('utf-8')
    # Use 'H' (unsigned short, 2 bytes per dimension)
    # Supports dimensions up to 65535
    shape_data = struct.pack('H' * len(shape), *shape)

    header = (bytes([len(dtype_bytes)]) + dtype_bytes +
              bytes([len(shape)]) + shape_data)

    return header + array.astype(dtype).tobytes()


def deserialize_array(data):
    """Deserialize bytes to numpy array with metadata.

    Parameters
    ----------
    data : bytes or numpy.ndarray
        Serialized data with metadata header (or numpy array from broker)

    Returns
    -------
    numpy.ndarray
        Deserialized array with correct dtype and shape
    """
    # Handle case where data is a numpy array (from broker payload)
    if isinstance(data, np.ndarray):
        data = data.tobytes()

    offset = 0

    # Read dtype
    dtype_len = data[offset]
    offset += 1
    dtype_str = data[offset:offset + dtype_len].decode('utf-8')
    offset += dtype_len

    # Read shape
    shape_len = data[offset]
    offset += 1
    if shape_len > 0:
        # Use 'H' (unsigned short, 2 bytes) for each dimension
        # Supports dimensions up to 65535
        shape = struct.unpack('H' * shape_len,
                              data[offset:offset + shape_len * 2])
        offset += shape_len * 2
    else:
        shape = ()

    # Read array data
    array_data = data[offset:]
    array = np.frombuffer(array_data, dtype=dtype_str)

    return array.reshape(shape)


class MessageBrokerForwarder:
    """Forwards message broker messages between testbeds over ZeroMQ.
    
    This operates on a separate thread after it is started. It subscribes to
    local message broker topics and forwards them to a remote testbed via ZeroMQ.
    
    Parameters
    ----------
    context : zmq.Context
        A previously-created ZMQ context. All sockets will be created on this context.
    message_broker : LocalMessageBroker
        The local message broker to subscribe to.
    publish_port : int
        The port number to publish forwarded messages on.
    topic_prefixes : list of str, optional
        List of exact topic names to forward. If None or empty, forwards nothing.
    """
    def __init__(self, context, message_broker, publish_port, topic_prefixes=None):
        self.context = context
        self.message_broker = message_broker
        self.publish_port = publish_port
        self.topics = topic_prefixes or []
        
        self.shutdown_flag = threading.Event()
        self.thread = None
        self.is_running = threading.Event()
        
        self.log = logging.getLogger(__name__)
        
        # Subscriptions for each topic prefix
        self.subscriptions = []
    
    def start(self):
        """Start the forwarder thread."""
        self.thread = threading.Thread(target=self._forwarder)
        self.thread.daemon = True
        self.thread.start()
        
        self.is_running.wait()
    
    def stop(self):
        """Stop the forwarder thread.
        
        This function waits until the thread is actually stopped.
        """
        self.shutdown_flag.set()
        
        if self.thread:
            self.thread.join()
        
        self.is_running.clear()
    
    def _forwarder(self):
        """Subscribe to local broker and forward messages via ZeroMQ.
        
        .. note::
            This function should not be called directly. Use
            :func:`start()` to start the forwarder.
        """
        # Create ZeroMQ publisher socket
        publisher = self.context.socket(zmq.PUB)
        
        # Retry bind a few times to avoid races / transient EADDRINUSE
        bind_ok = False
        for attempt in range(5):
            try:
                publisher.bind(f'tcp://*:{self.publish_port}')
                bind_ok = True
                self.log.info(f'Message broker forwarder bound to tcp://*:{self.publish_port}')
                break
            except Exception as e:
                self.log.warning(f'Attempt {attempt+1}: Failed to bind publisher to tcp://*:{self.publish_port}: {e}')
                time.sleep(0.1 * (attempt + 1))
        
        if not bind_ok:
            try:
                publisher.close()
            except Exception:
                pass
            self.log.error('Failed to bind message broker forwarder publisher')
            return
        
        # Subscribe to message broker topics
        from ..catkit_bindings import MessageSubscriptionMode
        
        try:
            for topic in self.topics:
                # Use Sequential to ensure we forward every message
                sub = self.message_broker.subscribe(
                    topic, 
                    mode=MessageSubscriptionMode.Sequential
                )
                self.subscriptions.append((topic, sub))
                self.log.info(f'Subscribed to message broker topic: {topic}')
        except Exception as e:
            self.log.error(f'Failed to subscribe to message broker topics: {e}')
            try:
                publisher.close()
            except Exception:
                pass
            return
        
        self.is_running.set()
        
        self.log.info(f'Forwarder started, monitoring {len(self.subscriptions)} topics')
        
        try:
            while not self.shutdown_flag.is_set():
                try:
                    # Poll each subscription for new messages
                    for topic, sub in self.subscriptions:
                        try:
                            # Non-blocking check for messages
                            msg = sub.get_next_message(timeout_in_sec=0.01)
                            
                            if msg is not None:
                                # Forward the message via ZeroMQ
                                # Format: [topic, frame_id, payload]
                                publisher.send_multipart([
                                    msg.topic.encode('utf-8'),
                                    str(msg.frame_id).encode('utf-8'),
                                    bytes(msg.payload)
                                ])
                        
                        except Exception as e:
                            error_str = str(e).lower()
                            # Ignore expected errors: timeout or service crash
                            if 'expired' in error_str:
                                # Normal timeout, continue
                                continue
                            elif 'appears to be inactive' in error_str:
                                # Service has crashed, stop this topic
                                self.log.info(
                                    f'Service inactive on {topic}, '
                                    f'stopping forwarder for this topic'
                                )
                                break
                            else:
                                # Unexpected error, log and continue
                                self.log.warning(
                                    f'Error getting message for {topic}: {e}'
                                )
                                continue
                    
                    # Small sleep to avoid busy-waiting
                    time.sleep(0.001)
                
                except Exception:
                    self.log.error(f'Error in forwarder loop: {traceback.format_exc()}')
                    time.sleep(0.1)
        
        finally:
            # Clean up
            try:
                publisher.close()
            except Exception:
                pass
            
            self.log.info('Message broker forwarder stopped')


class MessageBrokerReceiver:
    """Receives forwarded message broker messages and republishes them locally.
    
    This operates on a separate thread after it is started. It receives messages
    via ZeroMQ from remote testbeds and republishes them to the local message broker.
    
    Parameters
    ----------
    context : zmq.Context
        A previously-created ZMQ context. All sockets will be created on this context.
    message_broker : LocalMessageBroker
        The local message broker to publish to.
    remote_endpoints : list of str
        List of ZeroMQ endpoints to subscribe to (e.g., ['tcp://145.238.1.51:5555']).
    """
    def __init__(self, context, message_broker, remote_endpoints):
        self.context = context
        self.message_broker = message_broker
        self.remote_endpoints = remote_endpoints
        
        self.shutdown_flag = threading.Event()
        self.thread = None
        self.is_running = threading.Event()
        
        self.log = logging.getLogger(__name__)
    
    def start(self):
        """Start the receiver thread."""
        self.thread = threading.Thread(target=self._receiver)
        self.thread.daemon = True
        self.thread.start()
        
        self.is_running.wait()
    
    def stop(self):
        """Stop the receiver thread.
        
        This function waits until the thread is actually stopped.
        """
        self.shutdown_flag.set()
        
        if self.thread:
            self.thread.join()
        
        self.is_running.clear()
    
    def _receiver(self):
        """Receive messages via ZeroMQ and republish to local broker.
        
        .. note::
            This function should not be called directly. Use
            :func:`start()` to start the receiver.
        """
        # Create ZeroMQ subscriber socket
        subscriber = self.context.socket(zmq.SUB)
        subscriber.setsockopt(zmq.RCVTIMEO, 50)  # 50ms timeout
        subscriber.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
        
        # Connect to all remote endpoints
        for endpoint in self.remote_endpoints:
            try:
                subscriber.connect(endpoint)
                self.log.info(f'Message broker receiver connected to {endpoint}')
            except Exception as e:
                self.log.error(f'Failed to connect to {endpoint}: {e}')
        
        self.is_running.set()

        self.log.info('Receiver started, listening for messages')

        try:
            while not self.shutdown_flag.is_set():
                try:
                    # Receive forwarded message
                    try:
                        parts = subscriber.recv_multipart()
                    except zmq.Again:
                        # Timeout, check shutdown flag
                        continue
                    except zmq.ZMQError as e:
                        self.log.error(f'recv_multipart error: {e}')
                        continue
                    
                    if len(parts) != 3:
                        self.log.warning(f'Received malformed message with {len(parts)} parts')
                        continue
                    
                    # Parse message
                    topic = parts[0].decode('utf-8')
                    data = parts[2]

                    # Republish to local message broker with serialization intact
                    try:
                        # Publish the serialized data directly (preserves metadata)
                        self.message_broker.publish_data(topic, data)
                    except Exception as e:
                        self.log.error(f'Failed to republish: {e}')
                
                except Exception:
                    error_msg = traceback.format_exc()
                    self.log.error(f'Error in receiver loop: {error_msg}')
                    time.sleep(0.1)
        
        finally:
            # Clean up
            try:
                subscriber.close()
            except Exception:
                pass
            
            self.log.info('Message broker receiver stopped')
