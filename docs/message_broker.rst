Message Broker
==============

The Message Broker is a fundamental component of the catkit2 framework that enables efficient, high-performance message-based communication between processes. It provides a publish-subscribe messaging pattern that allows services to exchange data with minimal latency while maintaining flexibility in how consumers receive and process messages.

This documentation is divided into two parts. The first part describes the high-level interface for users of the Message Broker. The second part delves into the internal implementation details of the LocalMessageBroker for those interested in understanding how it achieves high performance and thread safety.

Part 1: User Guide
------------------

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

The MessageBroker Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The MessageBroker class defines the abstract interface for all message broker implementations. It provides methods for publishing data and creating subscriptions.

Publishing Data
^^^^^^^^^^^^^^^

The MessageBroker provides several methods for publishing data to topics:

- ``publish_data()``: Publishes raw binary data to a topic. This is the simplest way to send data.

- ``publish_array``: Publishes a NumPy array to a topic, preserving dtype, shape, and stride information.

- ``prepare_message()`` / ``publish_message()``: For advanced use cases, you can prepare a message first, populate it with data, and then publish it. This allows for zero-copy messaging.

Creating Subscriptions
^^^^^^^^^^^^^^^^^^^^^^

Subscriptions are created using the ``subscribe()`` method, which requires a topic name and a subscription mode (by default: NewestOnly). Subscriptions start at the current message and cannot retrieve messages from before they were created.

The Message Class
~~~~~~~~~~~~~~~~~

The Message class combines a payload (raw data) with a message header describing metadata. This metadata includes:

* **Topic** (127 chars): The hierarchical topic name
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

Message Properties
^^^^^^^^^^^^^^^^^^

Messages expose several read-only properties:

* **Topic**: The topic on which the message was published
* **Frame ID**: The unique sequential ID of the message within its topic
* **Payload ID**: A UUID uniquely identifying this payload
* **Trace ID**: A UUID that may be shared across related messages
* **Producer Information**: Hostname, process ID, and timestamp of the producer
* **Payload Size**: The total size of the payload in bytes

The MessageSubscription Class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The MessageSubscription class manages a consumer's subscription to a topic. It tracks which messages have been consumed and provides methods to retrieve the next message.

Retrieving Messages
^^^^^^^^^^^^^^^^^^^

- ``get_next_message()``: Blocks until the next message is available (or a timeout occurs). Returns the next message according to the subscription mode and updates the internal position tracker.

- ``try_get_next_message()``: Non-blocking variant that returns immediately. Returns the next message if available, or null if no new message exists.

Automatic Position Tracking
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Subscriptions automatically track the consumer's position using a preferred next message ID. Each successful retrieval updates this ID to the frame after the retrieved message, ensuring that sequential subscriptions receive every message exactly once.

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

    # Prepare a message for manual population
    message = broker.prepare_message("custom/topic", payload_size=1024)

    # Fill the payload
    message.payload[:] = np.arange(256, dtype=np.float32)

    # Add metadata
    message.set_metadata_entry("exposure", 100)
    message.set_metadata_entry("gain", 2.5)

    # Publish with a specific trace ID for tracking
    from catkit2.catkit_bindings import Uuid
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

When a producer calls ``prepare_message()``, the broker performs the following steps:

1. **Allocate Payload Memory**: The broker requests allocation for the given payload size and memory block ID. The HybridPoolAllocator for that memory block either serves the request from a thread-local pool or delegates to the underlying BuddyAllocator.

2. **Allocate Message Header**: A message header is allocated from the PoolAllocator. This is a simple atomic pop operation from the free list.

3. **Initialize Header**: The header is populated with:
   * Topic name
   * Generated payload ID and provided trace ID
   * Producer hostname and process ID
   * Payload location information (memory block, offset, size)
   * Reset metadata count to zero

4. **Return Message**: A Message object is constructed with the header pointer and payload address. The message is marked as unpublished.

Message Population
^^^^^^^^^^^^^^^^^^

Between preparation and publication, the producer can:

* Write data directly to the payload memory (obtained from shared memory)
* Set array metadata (dtype, shape, strides) for NumPy array support
* Add up to 12 metadata key-value pairs

This phase does not involve the broker; it is purely between the producer and the shared memory.

Message Publication
^^^^^^^^^^^^^^^^^^^

When ``publish_message()`` is called, the broker:

1. **Set Timestamp**: Records the current time in the message header.

2. **Hierarchical Routing**: Iterates through all subtopics of the message topic. For each subtopic:

   a. Obtain or create the TopicHeader for that subtopic
   b. Assign a frame ID (atomic increment of next_frame_id)
   c. If the circular buffer is full, remove the oldest message
   d. Store the message header index in the circular buffer
   e. Increment reference counts on both header and payload
   f. Update the last_frame_id to make the message visible
   g. Update the frame rate estimate for the topic

3. **Signal Consumers**: Wake any threads waiting for new messages via the Event notification system.

4. **Cleanup**: Decrement reference counts to release the producer's ownership. If the message is final, the message is complete. If not final, a new header is allocated for subsequent parts.

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

Design Characteristics
^^^^^^^^^^^^^^^^^^^^^^

The HashMap is designed with the following characteristics:

* **Fixed capacity**: The map is created with a fixed number of entries (16,384 for topic headers) and cannot grow dynamically
* **No deletions**: Once a topic is inserted, it remains in the map for the lifetime of the broker. This simplifies the concurrent access protocol
* **Fixed-size keys**: Keys are strings with a maximum length (127 characters for topic names)
* **Fixed-size values**: Each entry stores a value of fixed size (sizeof(TopicHeader))
* **Open addressing**: Uses linear probing for collision resolution rather than chaining

Hash Function
^^^^^^^^^^^^^

The HashMap uses MurmurHash3, a non-cryptographic hash function known for its excellent distribution properties and performance. The 32-bit implementation processes the key in 4-byte blocks, mixing the bits through a series of multiplications and bitwise operations to produce a well-distributed hash value. The hash is then taken modulo the number of entries to determine the starting index for the linear probe sequence.

Entry Structure
^^^^^^^^^^^^^^^

Each entry in the HashMap consists of three fields packed into a contiguous memory region:

* **Flags** (1 byte): An atomic state variable with three possible values:

  * **UNOCCUPIED** (0): The entry is available for insertion
  * **INITIALIZING** (1): A thread is currently inserting into this entry
  * **OCCUPIED** (2): The entry contains valid data and is ready for access

* **Key** (max_key_size bytes): The null-terminated string key
* **Value** (value_size bytes): The associated value (TopicHeader for the broker)

Entries are aligned to ensure the flags field is properly aligned for atomic operations.

Insertion Algorithm
^^^^^^^^^^^^^^^^^^^

Inserting a new topic follows a careful protocol to ensure thread safety:

1. Compute the hash of the key and determine the starting index
2. Linearly probe through entries until finding an available slot
3. Attempt to atomically transition the entry from UNOCCUPIED to INITIALIZING using CAS
4. If CAS succeeds:

   * Copy the key into the entry
   * Copy the value (if provided) into the entry
   * Atomically transition to OCCUPIED state
   * Return a pointer to the value

5. If CAS fails, another thread may have claimed the entry:

   * Spin-wait if the entry is in INITIALIZING state
   * If the entry is OCCUPIED and keys match, the topic already exists; return nullptr
   * Otherwise continue probing

The spin-wait on INITIALIZING entries handles the rare case where a thread is preempted during insertion. This can result in an infinite loop, but only occurs when there is a cache collision *and* a race condition at the same time, and then the thread that preempted us crashes. Effectively, this should never happen.

Lookup Algorithm
^^^^^^^^^^^^^^^^

Finding an existing topic is straightforward:

1. Compute the hash of the key and determine the starting index
2. Linearly probe through entries, checking each OCCUPIED entry for key equality
3. Return the value pointer when a match is found
4. Stop probing and return nullptr if an UNOCCUPIED entry is encountered (the key cannot exist beyond this point in the probe sequence)

The linear probing termination condition (stopping at UNOCCUPIED) relies on the fact that entries are never deleted. This ensures correctness while maintaining O(1) average-case lookup time.

Memory Ordering
^^^^^^^^^^^^^^^

The HashMap uses appropriate memory ordering to ensure visibility:

* Insertion uses **acquire-release** semantics on the CAS operation
* The transition to OCCUPIED uses **release** semantics to ensure all writes are visible to other threads
* Lookup uses **acquire** semantics when loading flags to ensure it sees all writes made by the inserting thread

This ensures that once a topic appears as OCCUPIED, all its data is fully initialized and visible to all threads.

Limitations
^^^^^^^^^^^

The HashMap has several limitations that are acceptable for the Message Broker use case:

* **No resizing**: The map must be created with sufficient capacity for all expected topics
* **No deletions**: Topics persist for the lifetime of the broker, though this aligns with the broker's design
* **Linear probing**: In pathological cases with many collisions, lookup time degrades to O(n), though MurmurHash3's good distribution makes this unlikely

For the Message Broker, these limitations are acceptable because the number of topics is bounded (by configuration and practical limits) and topics are long-lived.

The PoolAllocator
~~~~~~~~~~~~~~~~~

The PoolAllocator manages fixed-size blocks of memory using a lock-free concurrent stack. It is used exclusively for message header allocation.

Data Structures
^^^^^^^^^^^^^^^

The allocator maintains:

* **Head** (atomic uint32): Index of the first free block
* **Next array** (atomic uint32[]): Linked list of free blocks
* **RefCount array** (atomic size_t[]): Reference count for each block
* **Capacity**: Total number of blocks

All operations are lock-free, using compare-and-swap (CAS) loops for synchronization.

Allocation Algorithm
^^^^^^^^^^^^^^^^^^^^

To allocate a block:

1. Load the current head atomically
2. If head is INVALID_HANDLE, the pool is empty; return failure
3. Load the next pointer of the head block
4. Use CAS to update head to the next block
5. If CAS fails, another thread allocated or freed a block before us; retry from step 1
6. If CAS succeeds, increment the reference count of the allocated block
7. Return the block index

This algorithm is lock-free and wait-free for the uncontended case.

Deallocation Algorithm
^^^^^^^^^^^^^^^^^^^^^^

To release a block:

1. Decrement the reference count atomically
2. If the old count was not 1, other references exist; return
3. If the old count was 1, this thread is responsible for deallocation
4. Load the current head
5. Store the current head as the next pointer of the block being freed
6. Use CAS to update head to the freed block
7. If CAS fails, another thread allocated or freed a block; retry from step 4

The reference count ensures that a block is never returned to the free list while any thread holds a reference to it.

The BuddyAllocator
~~~~~~~~~~~~~~~~~~

The BuddyAllocator implements the buddy system memory allocation algorithm with enhancements for concurrent access. It manages variable-sized blocks that must be powers of two.

Binary Tree Representation
^^^^^^^^^^^^^^^^^^^^^^^^^^

Memory is represented as a binary tree stored in a flat array:

* The root (index 1) represents the entire memory pool
* For any node at index i, its children are at 2i and 2i+1
* Leaf nodes represent the minimum allocation size
* The depth of a node determines its block size: size = capacity / 2^level

Tree Node State
^^^^^^^^^^^^^^^

Each tree node stores its state in a packed 16-bit atomic integer:

* **Bits 0-14**: Reference count (up to 32767 concurrent references)
* **Bit 15 (REF_ZERO)**: Set when reference count reaches zero
* **Bit 14 (OCC)**: Node is fully occupied
* **Bit 13 (OCC_LEFT)**: Left child is occupied
* **Bit 12 (OCC_RIGHT)**: Right child is occupied
* **Bit 11 (COAL_LEFT)**: Left child is being coalesced
* **Bit 10 (COAL_RIGHT)**: Right child is being coalesced

This packing allows atomic updates to node state using single CAS operations.

Allocation Algorithm
^^^^^^^^^^^^^^^^^^^^

To allocate a block of given size:

1. Round size up to the next power of two
2. Calculate the tree level for this size: level = log2(capacity / size)
3. Calculate the range of node indices at this level
4. Starting from a rotating search point, iterate through nodes:

   a. Check if node is free using IsFree() on the state word
   b. If free, attempt to mark it occupied with CAS
   c. If CAS succeeds, mark all ancestors as having an occupied descendant
   d. If an ancestor is already marked occupied, rewind and retry

5. If no free node found, return failure

The rotating search start point (tracked per level) helps distribute allocations across the memory space and reduces contention.

Coalescing Protocol
^^^^^^^^^^^^^^^^^^^

Deallocation uses a three-phase protocol to safely merge buddies:

**Phase 1: Mark**
   Set coalescing flags on all ancestors to prevent concurrent allocations that might interfere with merging.

**Phase 2: Free**
   Atomically clear the occupied flag and reference count of the node being freed.

**Phase 3: Unmark**
   Clear coalescing flags on ancestors. If both buddies of a node are now free, they can be merged by clearing the parent's occupied flags.

The coalescing flags ensure that two threads cannot simultaneously try to merge overlapping regions, which could lead to race conditions.

Reference Counting
^^^^^^^^^^^^^^^^^^

The BuddyAllocator supports shared ownership of blocks:

* **Acquire**: Increment the reference count (bits 0-14)
* **Release**: Decrement the reference count
* When count reaches zero, set REF_ZERO flag and free the block
* CAS loop ensures that the thread setting REF_ZERO is the one that frees the block

This allows multiple consumers to share access to the same payload without coordination.

The HybridPoolAllocator
~~~~~~~~~~~~~~~~~~~~~~~

The HybridPoolAllocator combines a bitmap allocator and a buddy allocator to optimize for frequent allocations of a similar size by the same thread.

Two-Tier Design
^^^^^^^^^^^^^^^

Allocations are divided at a threshold (``min_size_pool``):

* **Small allocations** (below threshold): Served from pre-allocated pools
* **Large allocations** (above threshold): Delegated to BuddyAllocator

Pool Structure
^^^^^^^^^^^^^^

Each pool consists of 64 slots of the same size:

* **Bitmap** (uint64): Tracks which slots are occupied (1 = occupied)
* **Reference counters**: Array of 64 RefCounter objects for each slot

Pools are themselves allocated from the BuddyAllocator. Each pool holds 64 blocks of a specific size, aligned to that size.

Thread-Local Buckets
^^^^^^^^^^^^^^^^^^^^

To minimize contention, the allocator maintains thread-local buckets:

* Each thread has its own array of buckets, one per size level
* Each bucket contains a list of partially-filled pools for that size
* Threads allocate from their own buckets without synchronization

Composite Handle Encoding
^^^^^^^^^^^^^^^^^^^^^^^^^

The HybridPoolAllocator uses a unified handle space:

* For pooled allocations: ``handle = (pool_index << 6) | slot_index``
* For buddy allocations: ``handle = buddy_handle`` (direct pass-through)

The size determines which type of handle was used, allowing correct decoding during deallocation.

Allocation Algorithm
^^^^^^^^^^^^^^^^^^^^

To allocate a block:

1. Round size up to next power of two
2. If size >= ``min_size_pool``, delegate to BuddyAllocator
3. Calculate size level
4. Get thread-local bucket
5. For each pool in bucket (reverse order):

   a. Acquire pool reference
   b. Check if pool has free slots: ``~(pool.map) != 0``
   c. If yes, find first free slot: ``slot = ctz(~pool.map)``
   d. Set slot bit: ``pool.map |= (1 << slot)``
   e. If pool now full, remove from bucket
   f. Reset slot's reference counter
   g. Return composite handle: ``(pool_index << 6) | slot``
   h. If no, release pool and continue

6. If no pool available, allocate new pool from BuddyAllocator
7. Initialize pool with one slot occupied, add to bucket
8. Return handle for that slot

Deallocation Algorithm
^^^^^^^^^^^^^^^^^^^^^^

To release a block:

1. Decode handle to extract pool and slot indices
2. Get size from handle to determine if pooled or buddy
3. If buddy allocation, delegate to BuddyAllocator::Release
4. If pooled allocation:

   a. Get pool from pools array
   b. Decrement slot's reference counter
   c. If counter reached zero:

      i. If pool was full, add back to thread-local bucket
      ii. Clear slot bit: ``pool.map &= ~(1 << slot)``
      iii. Release pool reference
      iv. If pool.map is now zero:

          - Release pool reference again (pool is now free)
          - Remove pool from bucket if present
          - Pool will be reclaimed by BuddyAllocator

Performance Characteristics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Message Broker achieves high performance through several key design decisions:

- **Zero-Copy Access**
    Messages are stored in shared memory and accessed directly. No data copying occurs during publication or consumption.

- **Lock-Free Critical Paths**
    All allocation operations use lock-free algorithms. This ensures that even if a producer/consumer crashes during an allocation, the broker can continue to operate without it. However, memory owned by that process is irrevocably lost.

- **Efficient Memory Allocation Algorithms**
    * PoolAllocator: O(1) atomic stack operations
    * BuddyAllocator: O(log n) tree traversal with atomic state updates
    * HybridPoolAllocator: O(1) for pooled allocations, O(log n) for large Allocations

- **Minimal Thread Contention**
    The HybridPoolAllocator's thread-local buckets ensure that threads rarely contend for the same resources. Most allocations proceed without atomic operations on shared state.

- **Predictable Memory Usage**
    The circular buffer design ensures that memory usage remains bounded regardless of message production rate.

Limitations and Constraints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Message Header Limits**
    Maximum of 65,536 concurrent message headers across all topics. This is sufficient for most use cases but could be exceeded with many topics and slow consumers.

**Topic Buffer Size**
    Each topic maintains a circular buffer of 32 messages. Consumers that fall behind by more than 32 messages will miss data.

**Buddy Allocator Constraints**
    Both total capacity and minimum block size must be powers of two. Allocations are rounded up to the next power of two, which may result in internal fragmentation.

**Pool Size**
    HybridPoolAllocator pools contain 64 slots. This provides good granularity for small allocations but may not be optimal for all workloads.

**Topic Name Length**
    Topic names are limited to 127 characters.

**Local Only**
    The LocalMessageBroker operates only on a single machine. Cross-machine messaging requires additional infrastructure.

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
