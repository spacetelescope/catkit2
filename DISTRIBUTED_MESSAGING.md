# Distributed Messaging in CATKit2

## Overview

CATKit2 supports distributed messaging across multiple testbeds using **ZeroMQ (ØMQ)** and a custom serialization layer. This document explains how the system works, how to configure it, and how to use it in your testbed environment.

### Architecture Overview

```
Sender Testbed (camera-server):
┌─────────────────────────────────────────────────────────────┐
│  Service (e.g., dummy_camera)                               │
│  └─> Publishes image data via local message broker          │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│  LocalMessageBroker (Shared Memory)                          │
│  └─> Message storage & synchronization for local processes  │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│  MessageBrokerForwarder (Python)                             │
│  ├─> serialize_array() - Encode dtype & shape as metadata   │
│  └─> ZeroMQ PUB socket (tcp://*:5555)                       │
└─────────────────────────────────────────────────────────────┘
           ↓↓↓ NETWORK (TCP/IP) ↓↓↓
┌─────────────────────────────────────────────────────────────┐
│  MessageBrokerReceiver (Python)                              │
│  ├─> ZeroMQ SUB socket (tcp://host:5555)                    │
│  └─> Republish to local message broker (preserve metadata)  │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│  LocalMessageBroker (Shared Memory)                          │
│  └─> Message storage for recipient testbed                  │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│  Client (e.g., RemoteServiceProxy or local consumer)        │
│  ├─> deserialize_array() - Decode metadata & recover array  │
│  └─> Access remote image data transparently                 │
└─────────────────────────────────────────────────────────────┘

Receiver Testbed (main-server)
```

## Key Components

### 1. LocalMessageBroker (C++)
**Purpose**: Shared memory message storage and synchronization within a single testbed.

**Key Features**:
- Thread-safe message publishing and subscription
- Per-topic frame buffers with configurable size
- Optional Event notification for subscribers
- Atomic operations for frame IDs and metadata

**Configuration Constants** (in `catkit_core/LocalMessageBroker.h`):
```cpp
const size_t MIN_SIZE_POOL = 1024;        // Minimum memory pool size
const size_t TOPIC_MAX_NUM_MESSAGES = 32; // Max messages per topic
const size_t MAX_NUM_MESSAGES = 65536;    // Total message capacity
const size_t MAX_NUM_BLOCKS = 8192;       // Memory block capacity
const size_t MEMORY_ALIGNMENT = 32;       // Alignment for efficiency
```

### 2. DataStream (C++)
**Purpose**: Efficient per-frame data storage for high-frequency data (images, waveforms).

**Key Features**:
- Circular buffer for frame management
- Frame metadata (timestamps, IDs)
- Configurable number of frames in buffer
- Header stored in separate shared memory for efficiency

**Configuration Constants** (in `catkit_core/DataStream.h`):
```cpp
const size_t MAX_NUM_FRAMES_IN_BUFFER = 20;
const size_t DATASTREAM_HEADER_PADDING = 1024; // For alignment & future extensions
```

### 3. MessageBrokerForwarder (Python)
**Purpose**: Bridges local and remote testbeds via ZeroMQ network transport.

**Key Features**:
- Subscribes to local message broker topics
- Forwards messages via ZeroMQ PUB socket
- Preserves serialized data format (no re-serialization)
- Runs on separate thread to avoid blocking

**Serialization Format**:
```
[dtype_len(1B) | dtype_str | shape_len(1B) | shape_dims(2B each) | array_data]

Example for float64[240, 240]:
[7][float64][2][240][240][...pixel data...]
 ↑   ↑       ↑  ↑     ↑   ↑
 |   |       |  |     |   └─ Raw array bytes (460,800 bytes)
 |   |       |  |     └───── Second dimension (240)
 |   |       |  └───────── First dimension (240)
 |   |       └──────────── Number of dimensions (2)
 |   └─────────────────── dtype string
 └────────────────────── Length of dtype string (7 bytes)
```

**Supported Features**:
- All NumPy dtypes (float32, float64, uint8, uint16, int32, complex64, bool, etc.)
- Multi-dimensional arrays (up to 4D or more)
- Dimensions up to 65,535 elements per axis
- Special values (NaN, ±Inf) preserved exactly

### 4. MessageBrokerReceiver (Python)
**Purpose**: Receives ZeroMQ messages and republishes to local message broker.

**Key Features**:
- Subscribes to remote ZeroMQ PUB socket
- Republishes messages directly (preserves metadata)
- No deserialization overhead at receive time
- Lazy deserialization by clients

## Setup and Configuration

Each testbed uses a YAML configuration file (`testbed.yaml`) for distributed messaging setup.

#### Sender Testbed Configuration

```yaml
# testbed.yml on remote machine (camera-server)
default_port: 1234
startup_services:   # Services coordinated by main server
  - wfs_camera_1

# Message broker forwarding configuration  
remote_message_brokers:
  enabled: true
  forwarder:
    enabled: true
    publish_port: 5555  # Port to publish messages for main server
```

```yaml
wfs_camera_1:
  service_type: dummy_camera
  simulated_service_type: camera_sim
  interface: camera
  requires_safety: false
  remote_server: camera_server  # Run this service on the remote camera_server
  sensor_width: 240
  sensor_height: 240
  exposure_time: 500
  gain: 1.0
  width: 240
  height: 240
  offset_x: 0
  offset_y: 0
  flux: 2000.0
  acquisition_frame_rate: 30.0
  noise_level: 5.0
  signal_level: 2000.0
```

#### Receiver Testbed Configuration

```yaml
# testbed.yml on main server (main-server)
default_port: 1234
startup_services: []  # Services coordinated by this testbed

# Named remote testbeds configuration
remote_message_brokers:
  enabled: true
  connections:
    - name: camera_server
      endpoint: "tcp://145.238.1.51:1234"  # greenflash21
      forwarder_port: 5555  # Port where remote testbed publishes messages
      services:
        - wfs_camera_1
```

```yaml
wfs_camera_1:
  service_type: dummy_camera
  simulated_service_type: camera_sim
  interface: camera
  requires_safety: false
  sensor_width: 240
  sensor_height: 240
  exposure_time: 500
  gain: 1.0
  width: 240
  height: 240
  offset_x: 0
  offset_y: 0
  flux: 2000.0
  acquisition_frame_rate: 30.0
  noise_level: 5.0
  signal_level: 2000.0
```

## Usage Examples

### Example 1: Complete Sender Testbed Implementation

**File: `sender_testbed.py`**

```python
#!/usr/bin/env python3
"""
Sender testbed example - publishes camera images via distributed messaging.
"""

import sys
import logging
import time
import numpy as np
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main sender testbed entry point."""
    try:
        from catkit2.testbed import Testbed
        from catkit2.testbed.message_forwarder import (
            MessageBrokerForwarder,
            serialize_array
        )
        from catkit2.benchmark_constants import GIGABYTE
    except ImportError as e:
        logger.error(f"Failed to import CATKit2 modules: {e}")
        sys.exit(1)

    # Initialize testbed from configuration
    config_file = Path(__file__).parent / 'camera-server.yaml'
    logger.info(f"Loading configuration from {config_file}")
    
    testbed = Testbed.from_config_file(str(config_file))
    logger.info(f"Initialized testbed: {testbed.name}")

    # Start distributed messaging forwarder
    logger.info("Starting message forwarder...")
    try:
        testbed.start_distributed_messaging()
    except Exception as e:
        logger.error(f"Failed to start distributed messaging: {e}")
        sys.exit(1)

    # Publish sample data periodically
    logger.info("Starting data publisher loop...")
    frame_count = 0
    
    try:
        while True:
            # Generate sample camera image
            image = np.random.rand(240, 240).astype(np.float32)
            
            # Publish to local message broker (automatically forwarded)
            topic = 'camera/image/raw'
            serialized = serialize_array(image)
            
            try:
                testbed.message_broker.publish_array(topic, serialized)
                frame_count += 1
                
                if frame_count % 10 == 0:
                    logger.info(f"Published {frame_count} frames")
            except Exception as e:
                logger.warning(f"Failed to publish frame: {e}")
            
            # Sleep to maintain ~10 Hz frame rate
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("Shutdown signal received...")
    finally:
        logger.info(f"Shutting down... (published {frame_count} frames total)")
        testbed.shutdown()
        logger.info("Sender testbed stopped")

if __name__ == '__main__':
    main()
```

### Example 2: Complete Receiver Testbed Implementation

**File: `receiver_testbed.py`**

```python
#!/usr/bin/env python3
"""
Receiver testbed example - subscribes to remote camera images.
"""

import sys
import logging
import time
import numpy as np
from pathlib import Path
from collections import deque

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RemoteDataProcessor:
    """Processes remote data received from sender testbed."""
    
    def __init__(self, buffer_size=30):
        """Initialize data processor."""
        self.buffer_size = buffer_size
        self.frames = deque(maxlen=buffer_size)
        self.frame_count = 0
        self.error_count = 0
    
    def process_image(self, serialized_data):
        """Process received image data."""
        from catkit2.testbed.message_forwarder import deserialize_array
        
        try:
            # Deserialize the image
            image = deserialize_array(serialized_data)
            
            # Validate data
            if not isinstance(image, np.ndarray):
                logger.warning(f"Invalid image type: {type(image)}")
                self.error_count += 1
                return None
            
            # Store in buffer
            self.frames.append(image)
            self.frame_count += 1
            
            return image
        except Exception as e:
            logger.error(f"Failed to deserialize image: {e}")
            self.error_count += 1
            return None
    
    def get_statistics(self):
        """Get statistics on received frames."""
        if not self.frames:
            return None
        
        # Stack all frames
        stack = np.stack(list(self.frames))
        
        return {
            'frame_count': self.frame_count,
            'buffered_frames': len(self.frames),
            'shape': stack[0].shape,
            'dtype': stack.dtype,
            'mean': np.mean(stack),
            'std': np.std(stack),
            'min': np.min(stack),
            'max': np.max(stack),
            'error_count': self.error_count
        }

def main():
    """Main receiver testbed entry point."""
    try:
        from catkit2.testbed import Testbed
    except ImportError as e:
        logger.error(f"Failed to import CATKit2 modules: {e}")
        sys.exit(1)

    # Initialize testbed from configuration
    config_file = Path(__file__).parent / 'main-server.yaml'
    logger.info(f"Loading configuration from {config_file}")
    
    testbed = Testbed.from_config_file(str(config_file))
    logger.info(f"Initialized testbed: {testbed.name}")

    # Create data processor
    processor = RemoteDataProcessor(buffer_size=30)
    
    # Subscribe to remote camera topic
    def on_image_received(message):
        """Handle incoming image message."""
        try:
            image = processor.process_image(message.data)
            if image is not None and processor.frame_count % 10 == 0:
                stats = processor.get_statistics()
                logger.info(f"Received {stats['frame_count']} frames, "
                           f"mean={stats['mean']:.4f}, "
                           f"std={stats['std']:.4f}")
        except Exception as e:
            logger.error(f"Error processing image: {e}")
    
    # Start receiving
    logger.info("Starting message receiver...")
    try:
        testbed.start_distributed_messaging()
        testbed.subscribe('camera/image/raw', on_image_received)
    except Exception as e:
        logger.error(f"Failed to start receiver: {e}")
        sys.exit(1)

    # Monitor statistics
    logger.info("Receiver active, monitoring remote data...")
    last_stats = None
    
    try:
        while True:
            time.sleep(5)
            
            # Get and log statistics
            stats = processor.get_statistics()
            if stats and stats != last_stats:
                logger.info(f"Statistics - Frames: {stats['frame_count']}, "
                           f"Buffered: {stats['buffered_frames']}, "
                           f"Mean: {stats['mean']:.4f}, "
                           f"Std: {stats['std']:.4f}, "
                           f"Errors: {stats['error_count']}")
                last_stats = stats
    except KeyboardInterrupt:
        logger.info("Shutdown signal received...")
    finally:
        logger.info("Shutting down receiver...")
        testbed.shutdown()
        
        # Final statistics
        final_stats = processor.get_statistics()
        if final_stats:
            logger.info(f"Final statistics: {final_stats['frame_count']} frames "
                       f"received, {final_stats['error_count']} errors")
        
        logger.info("Receiver testbed stopped")

if __name__ == '__main__':
    main()
```

### Example 3: Custom Message Routing with Manual Control

**File: `custom_routing.py`**

```python
#!/usr/bin/env python3
"""
Advanced example - custom message routing with manual control.
"""

import sys
import logging
import time
import zmq
import numpy as np
from typing import Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CustomMessageRouter:
    """Custom router for selective topic forwarding."""
    
    def __init__(self, mode: str = 'forwarder'):
        """
        Initialize router.
        
        Parameters
        ----------
        mode : str
            'forwarder' for sender, 'receiver' for subscriber
        """
        self.mode = mode
        self.context = zmq.Context()
        self.socket = None
        self.running = False
    
    def start_forwarder(
        self,
        message_broker,
        publish_endpoint: str = "tcp://*:5555",
        topic_filters: Optional[List[str]] = None
    ):
        """
        Start message forwarder (sender side).
        
        Parameters
        ----------
        message_broker : LocalMessageBroker
            Local message broker instance
        publish_endpoint : str
            ZeroMQ endpoint to bind to
        topic_filters : List[str], optional
            Topic patterns to forward
        """
        logger.info(f"Starting forwarder on {publish_endpoint}")
        
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(publish_endpoint)
        
        # Set ZeroMQ options
        self.socket.setsockopt(zmq.SNDHWM, 1000)  # Send HWM
        self.socket.setsockopt(zmq.LINGER, 100)    # Linger on close
        
        self.topic_filters = topic_filters or ['*']
        self.message_broker = message_broker
        self.running = True
        
        logger.info(f"Forwarder ready, listening to topics: {self.topic_filters}")
        
        self._forward_messages()
    
    def start_receiver(
        self,
        message_broker,
        subscribe_endpoint: str = "tcp://camera-server:5555",
        topic_filters: Optional[List[str]] = None
    ):
        """
        Start message receiver (receiver side).
        
        Parameters
        ----------
        message_broker : LocalMessageBroker
            Local message broker instance
        subscribe_endpoint : str
            ZeroMQ endpoint to connect to
        topic_filters : List[str], optional
            Topic patterns to subscribe to
        """
        logger.info(f"Starting receiver connecting to {subscribe_endpoint}")
        
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(subscribe_endpoint)
        
        # Set ZeroMQ options
        self.socket.setsockopt(zmq.RCVHWM, 1000)   # Receive HWM
        self.socket.setsockopt(zmq.LINGER, 100)     # Linger on close
        
        # Subscribe to topics
        self.topic_filters = topic_filters or [b'']
        for topic in self.topic_filters:
            if isinstance(topic, str):
                topic = topic.encode('utf-8')
            self.socket.subscribe(topic)
            logger.info(f"Subscribed to topic: {topic.decode('utf-8', errors='ignore')}")
        
        self.message_broker = message_broker
        self.running = True
        
        self._receive_messages()
    
    def _forward_messages(self):
        """Forward messages from local broker to remote."""
        message_count = 0
        
        while self.running:
            try:
                # Simulate reading from message broker
                # In real implementation, subscribe to message broker topics
                time.sleep(1)
                
                message_count += 1
                if message_count % 10 == 0:
                    logger.info(f"Forwarded {message_count} messages")
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                logger.error(f"Error forwarding: {e}")
    
    def _receive_messages(self):
        """Receive and republish messages."""
        message_count = 0
        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        
        while self.running:
            try:
                # Poll with 1 second timeout
                events = dict(poller.poll(1000))
                
                if self.socket in events:
                    # Receive message
                    topic, payload = self.socket.recv_multipart()
                    
                    # Republish to local broker
                    topic_str = topic.decode('utf-8', errors='ignore')
                    try:
                        self.message_broker.publish_array(topic_str, payload)
                        message_count += 1
                        
                        if message_count % 10 == 0:
                            logger.info(f"Received and republished {message_count} messages")
                    except Exception as e:
                        logger.warning(f"Failed to republish: {e}")
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                logger.error(f"Error receiving: {e}")
    
    def stop(self):
        """Stop the router."""
        logger.info("Stopping router...")
        self.running = False
        if self.socket:
            self.socket.close()
        self.context.term()

def main():
    """Example usage."""
    logger.info("Custom Message Router Example")
    logger.info("This demonstrates manual router control")
    
    # In a real application:
    # from catkit2.testbed import Testbed
    # testbed = Testbed.from_config_file('config.yaml')
    # 
    # router = CustomMessageRouter(mode='forwarder')
    # router.start_forwarder(
    #     testbed.message_broker,
    #     topic_filters=['camera/*', 'sensor/*']
    # )

if __name__ == '__main__':
    main()
```

## Performance Characteristics

### Latency
- **Intra-testbed (local broker)**: < 1 ms (shared memory + event notifications)
- **Inter-testbed (ZeroMQ)**: 5-50 ms depending on network (typically 1 Gbps Ethernet)
- **Serialization overhead**: < 0.1 ms for typical few MB image (60KB payload)

### Throughput
- **Local broker**: Supports millions of messages per second
- **ZeroMQ forwarding**: Limited by network bandwidth and message size

### Memory Usage
- **Serialization header**: 10-20 bytes per array (dtype string + shape info)
- **Message broker overhead**: ~100 KB for metadata (topics, frame IDs, etc.)
- **Buffer allocation**: Scales linearly with configured buffer size (typically 1-2 GB)

## Troubleshooting

### Issue: "Connection refused" between testbeds
**Solution**:
1. Verify network connectivity: `ping camera-server.local`
2. Check firewall rules for port 5555 (or configured publish_port)
3. Verify ZeroMQ socket binding: Check logs for "Successfully bound" messages
4. Ensure sender testbed is running forwarder: Check `is_running()` status

### Issue: Data corruption or NaN values
**Solution**:
1. Verify dtype is correctly serialized: Print metadata in deserialize_array()
2. Check array shape matches: `print(f"Shape: {array.shape}")`
3. Verify no data truncation: Compare serialized byte count with expected
4. Enable debug logging in message_forwarder.py

### Issue: High latency between testbeds
**Solution**:
1. Check network latency: `ping -c 100 camera-server.local` and calculate std dev
2. Verify ZeroMQ TCP_KEEPALIVE settings (see ZeroMQ documentation)
3. Reduce message size or frequency if network is saturated
4. Consider multicast PUB-SUB for many subscribers (requires network support)

## Advanced Topics

### Custom Serialization Format

For specialized data types, extend the serialization layer:

```python
def serialize_custom(data, format_type='custom_v1'):
    """Custom serialization with format version tracking."""
    format_bytes = format_type.encode('utf-8')
    header = bytes([len(format_bytes)]) + format_bytes
    
    # Custom encoding logic
    encoded_data = custom_encode(data)
    
    return header + encoded_data

def deserialize_custom(data):
    """Recover custom format with backward compatibility."""
    offset = 0
    format_len = data[offset]
    offset += 1
    
    format_type = data[offset:offset + format_len].decode('utf-8')
    offset += format_len
    
    if format_type == 'custom_v1':
        return custom_decode_v1(data[offset:])
    elif format_type == 'custom_v2':
        return custom_decode_v2(data[offset:])
    else:
        raise ValueError(f"Unknown format: {format_type}")
```

## Best Practices

1. **Buffer Sizing**: Allocate 1-2 GB for message broker unless you have specific requirements. Too small causes message loss; too large wastes memory.

2. **Frame Rates**: For camera data, match the sender's frame rate on the receiver. Mismatch causes buffering issues.

3. **Topic Naming**: Use hierarchical topic names (`service/component/property`) for logical organization and selective forwarding.

4. **Error Handling**: Always wrap deserialization in try-except blocks; network data can be corrupted.

5. **Resource Cleanup**: Explicitly call `forwarder.stop()` and `receiver.stop()` in shutdown handlers to prevent resource leaks.

6. **Monitoring**: Log forwarder/receiver status periodically to detect connection issues early.

## Constants Reference

### C++ (catkit_core)
| Constant | Value | Purpose |
|----------|-------|---------|
| `MIN_SIZE_POOL` | 1024 | Minimum memory pool allocation |
| `TOPIC_HASH_MAP_SIZE` | 16384 | Hash table size for topics |
| `TOPIC_MAX_NUM_MESSAGES` | 32 | Max messages buffered per topic |
| `MAX_NUM_MESSAGES` | 65536 | Total message capacity |
| `MAX_NUM_BLOCKS` | 8192 | Memory block limit |
| `MEMORY_ALIGNMENT` | 32 | Cache line alignment |
| `MAX_NUM_FRAMES_IN_BUFFER` | 20 | DataStream frame buffer depth |
| `DATASTREAM_HEADER_PADDING` | 1024 | Header buffer padding/alignment |

### Python
| Constant | Value | Purpose |
|----------|-------|---------|
| `GIGABYTE` | 1024³ | 1 GB in bytes |
| `MEGABYTE` | 1024² | 1 MB in bytes |
| `DEFAULT_PUBLISH_PORT` | 5555 | ZeroMQ PUB socket port |
| `DEFAULT_MESSAGE_BROKER_BUFFER` | 2 GB | Typical buffer size |

## References

- [ZeroMQ Guide](https://zguide.zeromq.org/)
- [NumPy Serialization](https://numpy.org/doc/stable/reference/arrays.bytes.html)
- [CATKit2 Services Documentation](./docs/services.rst)
- [Message Broker Protocol](./docs/protocol.rst)

---

*Last updated: October 2025*
*For issues or questions, refer to the [CATKit2 GitHub repository](https://github.com/spacetelescope/catkit2)*
