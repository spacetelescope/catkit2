Message Broker
==============

The Message Broker is a fundamental component of the catkit2 framework that enables efficient, high-performance message-based communication between processes. It provides a publish-subscribe messaging pattern that allows services to exchange data with minimal latency while maintaining flexibility in how consumers receive and process messages.

This documentation is divided into two parts. The first part describes the high-level interface for users of the Message Broker. The second part delves into the internal implementation details of the LocalMessageBroker for those interested in understanding how it achieves high performance and thread safety.

Quick Start
-----------

Here is a minimal example of using the Message Broker to publish and subscribe to messages:

.. code-block:: python

    from catkit2.catkit_bindings import LocalMessageBroker, LocalMemory, MessageSubscriptionMode
    import numpy as np

    # Create the broker with memory blocks
    header_memory = LocalMemory.create(10 * 1024 * 1024)    # 10 MB for headers
    payload_memory = LocalMemory.create(100 * 1024 * 1024)  # 100 MB for payloads
    broker = LocalMessageBroker.create(header_memory, [payload_memory])

    # Publish a message
    image = np.random.randn(1024, 1024).astype(np.float32)
    broker.publish_array("camera/image", image)

    # Subscribe and receive messages
    subscription = broker.subscribe("camera/image", mode=MessageSubscriptionMode.NewestOnly)
    message = subscription.get_next_message(timeout=1.0)
    if message:
        print(f"Received: {message.payload.shape}")

Part 1: User Guide
------------------

System Constraints
~~~~~~~~~~~~~~~~~~

Before designing your system, be aware of these limitations:

**Message Header Limits**
    Maximum of 65,536 concurrent message headers across all topics. This is sufficient for most use cases but could be exceeded with many topics and slow consumers.

**Topic Buffer Size**
    Each topic maintains a circular buffer of 32 messages. Consumers that fall behind by more than 32 messages will miss data.

**Topic Name Length**
    Topic names are limited to 127 characters (126 usable characters plus null terminator).

**Local Only**
    The LocalMessageBroker operates only on a single machine. Cross-machine messaging requires additional infrastructure.

**Metadata Limits**
    Each message can carry up to 12 metadata entries with keys up to 7 characters and string values up to 8 characters.

Overview
~~~~~~~~

The Message Broker enables communication between different processes using a topic-based publish-subscribe model. Services can publish messages to named topics, and other services can subscribe to those topics to receive the data. This decouples producers from consumers, allowing them to operate independently.

Key Concepts
~~~~~~~~~~~~

Topics
^^^^^^

Messages are organized into topics, which are identified by hierarchical names using forward slashes as separators. For example, ``camera1/images/get`` represents a topic for raw images from camera 1. The hierarchical structure allows for flexible subscription patterns.

Messages
^^^^^^^^

A message consists of a payload (the actual data) and associated metadata. Messages contain:

* Raw binary data
* Dtype and shape information
* Metadata key-value pairs (integers, floats, or short strings)
* A trace ID for tracking related messages

Each message is assigned a unique frame ID within its topic, allowing consumers to track message ordering and detect dropped messages.

Subscriptions
^^^^^^^^^^^^^

Consumers receive messages by creating subscriptions to topics. The Message Broker supports two subscription modes:

**NewestOnly**: Always delivers the most recent message, skipping older messages if the consumer falls behind. This mode is ideal for real-time displays that only need current data.

**Sequential**: Delivers every message in order without skipping. If a consumer falls behind, it will receive all buffered messages. This mode is essential for logging and data recording.

Subscriptions are created using the ``subscribe()`` method, which requires a topic name and a subscription mode (default: NewestOnly). Subscriptions start at the current message and cannot retrieve messages from before they were created.

The MessageSubscription Class
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The MessageSubscription class manages a consumer's subscription to a topic and provides methods to retrieve messages:

- ``get_next_message()``: Blocks until the next message is available (or a timeout occurs). Returns the next message according to the subscription mode.

- ``try_get_next_message()``: Non-blocking variant that returns immediately. Returns the next message if available, or null if no new message exists.

Subscriptions automatically track the consumer's position using a preferred next message ID. Each successful retrieval updates this ID to the frame after the retrieved message, ensuring that sequential subscriptions receive every message exactly once.

The MessageBroker Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The MessageBroker class defines the abstract interface for all message broker implementations. It provides methods for publishing data and creating subscriptions.

Publishing Data
^^^^^^^^^^^^^^^

The MessageBroker provides several methods for publishing data to topics:

- ``publish_data()``: Publishes raw binary data to a topic. This is the simplest way to send data.

- ``publish_array()``: Publishes a NumPy array to a topic, preserving dtype, shape, and stride information.

- ``prepare_message()`` / ``publish_message()``: For advanced use cases, you can prepare a message first, populate it with data, and then publish it. This allows for zero-copy messaging.

The Message Class
~~~~~~~~~~~~~~~~~

The Message class combines a payload (raw data) with a message header describing metadata. This metadata includes:

* **Topic** (126 chars): The hierarchical topic name (127 bytes including null terminator)
* **Payload ID** (UUID): Unique identifier for the payload
* **Trace ID** (UUID): Identifier shared across related messages
* **Producer Hostname** (64 chars): The machine that produced the message
* **Producer PID**: The process ID of the producer
* **Producer Timestamp**: Nanoseconds since epoch when published
* **Payload Info**: Memory block ID, block handle, offset, and total size
* **Array Info**: Dtype, shape, and strides for NumPy arrays
* **Partial Frame ID**: For multi-part messages
* **Metadata Entries**: Up to 12 key-value pairs

Accessing Payload Data
^^^^^^^^^^^^^^^^^^^^^^

The message payload is always accessed as a NumPy array with preserved dtype and shape information. If data was submitted, the resulting Numpy array is one-dimensional with dtype ``uint8``.

Metadata Access
^^^^^^^^^^^^^^^

Each message can carry up to 12 metadata entries. Each entry has:

* A key (up to 7 characters)
* A value (integer, float, or string up to 8 characters)

Usage Examples
~~~~~~~~~~~~~~

Publishing Data
^^^^^^^^^^^^^^^

.. code-block:: python

    from catkit2.catkit_bindings import LocalMessageBroker, LocalMemory

    # Create memory blocks for the broker
    header_memory = LocalMemory.create(1024 * 1024 * 10)  # 10 MB for headers
    payload_memory = LocalMemory.create(1024 * 1024 * 100)  # 100 MB for payloads

    # Create the broker
    broker = LocalMessageBroker.create(header_memory, [payload_memory])

    # Publish raw bytes
    data = b"Hello, World!"
    broker.publish_data("greetings/hello", data)

    # Publish a NumPy array
    import numpy as np
    image = np.random.randn(1024, 1024).astype(np.float32)
    broker.publish_array("camera/image", image)

Subscribing to Messages
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from catkit2.catkit_bindings import MessageSubscriptionMode

    # Subscribe to receive only the newest messages
    sub_newest = broker.subscribe("camera/image", mode=MessageSubscriptionMode.NewestOnly)

    # Subscribe to receive all messages in sequence
    sub_sequential = broker.subscribe("camera/image", mode=MessageSubscriptionMode.Sequential)

    # Get the next message (blocks until available)
    message = sub_sequential.get_next_message(timeout=1.0)
    if message:
        print(f"Received frame {message.frame_id} on topic {message.topic}")
        print(f"Payload shape: {message.payload.shape}")

Advanced Message Handling
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from catkit2.catkit_bindings import Uuid
    import numpy as np

    # Prepare a message for manual population
    message = broker.prepare_message("custom/topic", payload_size=1024)

    # Fill the payload
    message.payload[:] = np.arange(256, dtype=np.float32)

    # Add metadata
    message.set_metadata_entry("exposure", 100)
    message.set_metadata_entry("gain", 2.5)

    # Publish with a specific trace ID for tracking
    trace_id = Uuid()
    broker.publish_message(message, trace_id=trace_id)

Part 2: Implementation Details
------------------------------

This section describes the internal implementation of the LocalMessageBroker. It is intended for developers who want to understand how the Message Broker achieves high performance and thread safety.

Architecture Overview
~~~~~~~~~~~~~~~~~~~~~

The LocalMessageBroker is the concrete implementation of the MessageBroker interface. It operates entirely within shared memory, making it accessible to multiple processes on the same machine.

Key design principles:

* **Zero-copy**: Messages are stored in shared memory and accessed directly by consumers
* **Lock-free**: Critical paths use atomic operations rather than mutexes
* **Reference counting**: Old messages are automatically reclaimed

Memory Management Strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The LocalMessageBroker uses two distinct allocators for different purposes:

- **Message Headers** are fixed-size structures containing metadata. They are allocated from a PoolAllocator, which provides O(1) lock-free allocation and deallocation for fixed-size blocks.

- **Message Payloads** vary in size and are allocated from HybridPoolAllocators. Each memory block managed by the broker has its own HybridPoolAllocator, which optimizes for small, frequent allocations while supporting larger payloads efficiently.

Message Lifecycle
~~~~~~~~~~~~~~~~~

Understanding how messages flow through the system requires examining three key operations: preparation, population, and publication.

Message Preparation
^^^^^^^^^^^^^^^^^^^

When ``prepare_message()`` is called, the broker allocates payload memory using the HybridPoolAllocator, allocates a message header from the PoolAllocator, and initializes the header with topic name, IDs, producer information, and payload location. The resulting Message object provides direct access to the payload memory in shared memory.

Message Population
^^^^^^^^^^^^^^^^^^

Between preparation and publication, the producer writes data directly to the payload memory, sets array metadata for NumPy support, and adds up to 12 metadata entries. This phase requires no broker involvement.

Message Publication
^^^^^^^^^^^^^^^^^^^

When ``publish_message()`` is called, the broker timestamps the message, routes it through the topic hierarchy by updating each subtopic's circular buffer with atomic operations, increments reference counts, signals waiting consumers via the Event system, and releases the producer's ownership reference.

The TopicHeader Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~

Each topic maintains a TopicHeader in a concurrent hash map:

* **next_frame_id** (atomic): The ID to assign to the next message
* **first_frame_id** (atomic): The oldest message still available
* **last_frame_id** (atomic): One past the newest message
* **frame_rate**: Estimated message rate using exponential decay
* **message_headers**: Circular buffer of up to 32 message header indices

The circular buffer design provides predictable memory usage and allows consumers to access recent message history.

Reference Counting
~~~~~~~~~~~~~~~~~~

Both message headers and payloads use reference counting to manage lifetime:

* When a message is published, reference counts are incremented for each topic that carries it
* When a message is removed from a topic's circular buffer, the reference count is decremented
* When the reference count reaches zero, the memory is returned to the allocator

This design ensures that messages remain valid as long as any consumer is accessing them, even if the producer has moved on.

The HashMap
~~~~~~~~~~~

The LocalMessageBroker uses a lock-free concurrent HashMap to store and retrieve TopicHeaders. This data structure enables efficient lookup of topics by name while supporting concurrent access from multiple threads.

The HashMap is designed with the following characteristics:

* **Fixed capacity**: The map is created with a fixed number of entries (16,384 for topic headers) and cannot grow dynamically
* **No deletions**: Once a topic is inserted, it remains in the map for the lifetime of the broker
* **Fixed-size keys**: Keys are strings with a maximum length (127 characters for topic names)
* **Open addressing**: Uses linear probing with MurmurHash3 for collision resolution

Entries use a three-state atomic flag (UNOCCUPIED, INITIALIZING, OCCUPIED) to coordinate concurrent insertions. All operations are lock-free using compare-and-swap primitives.

The PoolAllocator
~~~~~~~~~~~~~~~~~

The PoolAllocator manages fixed-size blocks of memory using a lock-free concurrent stack. It is used exclusively for message header allocation.

The allocator maintains a linked list of free blocks accessed atomically via compare-and-swap operations. Each block has a reference count to ensure memory is only reclaimed when all references are released. This provides O(1) allocation and deallocation performance.

The BuddyAllocator
~~~~~~~~~~~~~~~~~~

The BuddyAllocator implements the buddy system memory allocation algorithm with enhancements for concurrent access. It manages variable-sized blocks that must be powers of two.

Memory is represented as a binary tree where each node tracks occupation state and reference counts in a packed 16-bit atomic integer. Allocation uses a rotating search pattern to distribute memory evenly and reduce contention. Deallocation employs a three-phase coalescing protocol to safely merge adjacent free blocks while preventing race conditions.

The HybridPoolAllocator
~~~~~~~~~~~~~~~~~~~~~~~

The HybridPoolAllocator combines a bitmap allocator and a buddy allocator to optimize for frequent allocations of a similar size by the same thread.

Small allocations (below a configurable threshold) are served from thread-local pools, while larger allocations are delegated to the BuddyAllocator. Each pool contains 64 slots tracked by a bitmap. Thread-local buckets minimize contention by allowing threads to allocate from their own pools without synchronization.

Thread Safety
~~~~~~~~~~~~~

The LocalMessageBroker is fully thread-safe:

* Multiple threads can publish to the same or different topics concurrently
* Multiple threads can subscribe to and consume from the same topic concurrently
* Publishers and consumers can operate simultaneously without coordination
* All allocators support concurrent allocation and deallocation

Memory ordering is carefully managed to ensure visibility of changes across threads while maximizing performance.

Conclusion
~~~~~~~~~~

The LocalMessageBroker provides a robust, high-performance foundation for inter-process communication. The sophisticated memory management system, built on lock-free PoolAllocator, BuddyAllocator, and HybridPoolAllocator components, ensures efficient and scalable operation for message payloads of all sizes.
