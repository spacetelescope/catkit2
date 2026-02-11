# Network Message Broker Design Document

## Overview

This document describes a **fully synchronous remote message broker** that implements the `MessageBroker` interface. Unlike the original async mesh design, all operations are request-response, making the implementation simpler and more predictable. This design is suitable for remote displays and monitoring at moderate frame rates (10-60Hz), not for high-frequency streaming (2kHz).

## Architecture

The `RemoteMessageBroker` implements the `MessageBroker` interface, providing transparent access to both local and remote topics:

```
Application
    │
    ▼
┌─────────────────────┐
│ RemoteMessageBroker │◄── Implements MessageBroker interface
│   (synchronous)     │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌──────────┐ ┌──────────┐
│  Local   │ │  Client  │
│  Broker  │ │ (existing│
│ (shared) │ │  class)  │
└──────────┘ └────┬─────┘
                  │
            ┌─────┴─────┐
            │  Network  │
            └─────┬─────┘
                  │
            ┌─────┴─────┐
            │  Server   │
            │(existing  │
            │  class)   │
            └───────────┘
```

## Key Design Decisions

### 1. Fully Synchronous Operations

All `MessageBroker` operations become synchronous network calls:

| Operation | Local | Remote |
|-----------|-------|--------|
| `PrepareMessage()` | Local shared memory | Allocate local buffer, send to remote on publish |
| `PublishMessage()` | Local publish | Serialize and send to remote via REQ/REP |
| `GetNextMessage()` | Local wait | Network round-trip request |
| `GetCurrentMessage()` | Local read | Network round-trip request |
| `Subscribe()` | Local subscription | No-op (GetNextMessage handles fetching) |

### 2. Topic Routing

**All topics use the machine prefix**: `{machine_name}/{topic_path}`

```cpp
// Example topics
machine1/camera/stream     // Camera stream on machine1
machine1/telemetry         // Telemetry on machine1
machine2/sensor/data       // Sensor data on machine2
```

**Routing decision based on machine name:**
```cpp
// If topic starts with local machine name → Use LocalMessageBroker
machine1/camera/stream on machine1 → LocalMessageBroker

// If topic starts with different machine name → Use network Client
machine2/sensor/data on machine1 → Client to machine2
```

**Note**: All topics use the full `{machine}/{topic}` form consistently, whether local or remote.

### 3. Communication Layer

**Reuses existing Client/Server classes**:

- **Client**: Handles REQ socket connection pooling, timeouts, and request serialization
- **Server**: Handles REP socket, request dispatch via thread pool

**Server Thread Pool (Built-in)**:
The `Server` class now includes a configurable thread pool (default: 1 worker). Instead of ZMQ's round-robin proxy (which would block all workers if one GET_NEXT takes a long time), it uses `std::queue` + `std::mutex`:
- Main thread (ReceiveLoop) receives requests from ZMQ and enqueues them
- Worker threads (WorkerLoop) dequeue and process independently
- **Thread safety**: ZMQ sockets are not thread-safe, so `SendResponse()` uses a mutex to protect socket operations
- Constructor parameter: `Server(int port, int num_workers = 1)`

**Example:**
```cpp
// Single-threaded (backward compatible)
Server server1(5001);

// Multi-threaded with 4 workers
Server server2(5001, 4);
```

**Benefits**:
- Already tested and optimized (socket pooling, reconnection)
- Consistent with existing codebase
- Thread-safe Client class
- Request isolation - long operations don't block others

**One Client per peer**: Each `RemoteMessageBroker` maintains one `Client` object per remote machine.

### 4. No Background Threads (Client-side)

Unlike the async design, the client-side has no background threads. All operations are synchronous:
- `PrepareMessage()` allocates a temporary local buffer (for remote topics)
- `PublishMessage()` blocks until remote ACK
- `GetNextMessage()` blocks until response or timeout
- `Subscribe()` returns immediately (just creates MessageSubscription object)

**Server-side**: Uses thread pool to handle concurrent requests from multiple clients.

## Data Flow

### Publishing to Remote Topic

```
App calls PublishMessage("machine1/sensor", data)
    ↓
RemoteMessageBroker detects remote topic
    ↓
Serialize message to string
    ↓
client->MakeRequest("PUBLISH", serialized_data)
    ↓
Wait for response (blocking, 60s timeout)
    ↓
Return (success or error)
```

### Getting Message from Remote Topic

```
App calls subscription.GetNextMessage(timeout)
    ↓
RemoteMessageBroker::GetNextMessage("machine1/sensor", ...)
    ↓
Serialize request to string
    ↓
client->MakeRequest("GET_NEXT", serialized_request)
    ↓
Wait for response (blocking, with timeout)
    ↓
Deserialize response to Message object
    ↓
Return message or nullopt
```

## Protocol

Uses the existing Client/Server protocol (string-based request-response):

### Request Format

```
Request:  [type: string, data: string]
          type = "PUBLISH", "GET_NEXT", "GET_CURRENT", "GET_RATE", "LIST_TOPICS"
          data = serialized request parameters

Response: [status: "OK" or "ERROR", data: string]
          status = operation result
          data = serialized response or error message
```

### Request Types

**PUBLISH:**
```cpp
// Request data: Serialized message (header + payload)
// Response: "OK" or error message
client->MakeRequest("PUBLISH", SerializeMessage(msg));
```

**GET_NEXT:**
```cpp
// Request data: topic + frame_id + mode + timeout
struct GetNextParams {
    std::string topic;          // e.g., "camera/stream"
    uint64_t preferred_frame_id;
    uint32_t mode;              // 0=NewestOnly, 1=Sequential
    double timeout_seconds;
};
// Response: Empty string (nullopt) or serialized Message
std::string response = client->MakeRequest("GET_NEXT", Serialize(params));
```

**GET_CURRENT:**
```cpp
// Request data: topic string
// Response: Empty string (no message) or serialized Message
std::string response = client->MakeRequest("GET_CURRENT", "camera/stream");
```

**GET_RATE:**
```cpp
// Request data: topic string
// Response: rate as string (e.g., "100.5")
std::string response = client->MakeRequest("GET_RATE", "camera/stream");
```

**LIST_TOPICS:**
```cpp
// Request data: empty or filter string
// Response: JSON array of topic names
std::string response = client->MakeRequest("LIST_TOPICS", "");
```

## Implementation

### RemoteMessageBroker Class

```cpp
#include "Client.h"

class RemoteMessageBroker : public MessageBroker {
public:
    RemoteMessageBroker(LocalMessageBroker* local_broker,
                        const std::vector<PeerConfig>& peers);

    // MessageBroker interface
    Message PrepareMessageImpl(std::string_view topic, size_t payload_size,
                               Uuid trace_id, uint8_t memory_block_id = 0) override;
    Message PublishMessage(Message message, bool is_final = true) override;
    std::optional<Message> GetCurrentMessage(std::string_view topic) override;
    std::optional<Message> GetNextMessage(std::string_view topic,
                                           size_t preferred_next_frame_id,
                                           MessageSubscriptionMode mode = MessageSubscriptionMode::NewestOnly,
                                           double timeout_in_seconds = -1,
                                           EventWaitMethod wait_type = EventWaitMethod::Default,
                                           void (*error_check)() = nullptr) override;
    std::optional<Message> TryGetNextMessage(std::string_view topic,
                                              size_t preferred_next_frame_id,
                                              MessageSubscriptionMode mode = MessageSubscriptionMode::NewestOnly) override;
    std::vector<std::string> GetAllMessageTopics() override;
    double GetMessageRate(std::string_view topic) override;

private:
    LocalMessageBroker* m_LocalBroker;
    std::unordered_map<std::string, std::unique_ptr<Client>> m_PeerClients;  // machine_name → Client
    
    // Temporary buffers for remote messages (until published)
    std::unordered_map<std::string, std::vector<uint8_t>> m_TempBuffers;

    bool IsLocalTopic(std::string_view topic);
    std::string GetMachineFromTopic(std::string_view topic);
    Client& GetClientForMachine(const std::string& machine);

    // Serialization helpers
    std::string SerializeMessage(const Message& msg);
    std::string SerializeGetNextRequest(const std::string& topic, uint64_t frame_id,
                                        int mode, double timeout);
    std::optional<Message> DeserializeMessage(const std::string& data);
};
```

### PrepareMessage for Remote Topics

For remote topics, `PrepareMessage` allocates a **temporary local buffer** instead of shared memory:

```cpp
Message RemoteMessageBroker::PrepareMessageImpl(std::string_view topic, 
                                                 size_t payload_size,
                                                 Uuid trace_id, 
                                                 uint8_t memory_block_id) {
    if (IsLocalTopic(topic)) {
        // Local topic: use LocalMessageBroker's shared memory
        return m_LocalBroker->PrepareMessageImpl(topic, payload_size, trace_id, memory_block_id);
    } else {
        // Remote topic: allocate temporary heap buffer
        std::string topic_str(topic);
        m_TempBuffers[topic_str] = std::vector<uint8_t>(payload_size);
        void* buffer = m_TempBuffers[topic_str].data();
        
        // Create Message wrapper around temporary buffer
        // Message will be serialized and sent on PublishMessage
        return CreateMessageFromBuffer(topic, buffer, payload_size, trace_id);
    }
}
```

**Key points:**
- Local topics use shared memory (fast, zero-copy)
- Remote topics use heap buffers (serialized on publish)
- Temporary buffers freed after successful publish or on broker destruction

### RemoteBrokerServer Class

The server uses a **thread pool with std::queue and std::mutex** instead of ZMQ's round-robin proxy. This prevents slow operations (like GET_NEXT with long timeouts) from blocking other requests:

```cpp
#include "Server.h"
#include <queue>
#include <mutex>
#include <condition_variable>
#include <thread>

struct PendingRequest {
    std::string client_identity;
    std::string request_id;
    std::string request_type;
    std::string request_data;
};

class RemoteBrokerServer {
public:
    RemoteBrokerServer(LocalMessageBroker* broker, uint16_t port, int num_workers = 4);
    void Start();  // Non-blocking, starts threads
    void Stop();

private:
    LocalMessageBroker* m_Broker;
    Server m_Server;
    int m_NumWorkers;
    
    // Request queue (producer: main thread, consumers: worker threads)
    std::queue<PendingRequest> m_RequestQueue;
    std::mutex m_QueueMutex;
    std::condition_variable m_QueueCV;
    std::atomic<bool> m_Running;
    
    std::vector<std::thread> m_WorkerThreads;
    std::thread m_ReceiveThread;
    
    void ReceiveLoop();      // Main thread: receive from ZMQ, enqueue
    void WorkerLoop();       // Worker threads: dequeue and process
    
    // Request handlers
    std::string HandlePublish(const std::string& request_data);
    std::string HandleGetNext(const std::string& request_data);
    std::string HandleGetCurrent(const std::string& request_data);
    std::string HandleGetRate(const std::string& request_data);
    std::string HandleListTopics(const std::string& request_data);
};

// Thread pool implementation
void RemoteBrokerServer::ReceiveLoop() {
    while (m_Running) {
        // Receive from ZMQ (non-blocking or with timeout)
        auto [identity, req_id, type, data] = m_Server.ReceiveRequest();
        
        if (!type.empty()) {
            // Enqueue for workers
            std::lock_guard lock(m_QueueMutex);
            m_RequestQueue.push({identity, req_id, type, data});
            m_QueueCV.notify_one();
        }
    }
}

void RemoteBrokerServer::WorkerLoop() {
    while (m_Running) {
        PendingRequest req;
        
        // Dequeue (blocking)
        {
            std::unique_lock lock(m_QueueMutex);
            m_QueueCV.wait(lock, [this] { return !m_RequestQueue.empty() || !m_Running; });
            
            if (!m_Running) break;
            
            req = m_RequestQueue.front();
            m_RequestQueue.pop();
        }
        
        // Process (can block for long time, doesn't affect other workers)
        std::string response;
        try {
            if (req.request_type == "PUBLISH") {
                response = HandlePublish(req.request_data);
            } else if (req.request_type == "GET_NEXT") {
                response = HandleGetNext(req.request_data);  // May take seconds
            } // ... etc
        } catch (const std::exception& e) {
            response = std::string("ERROR: ") + e.what();
        }
        
        // Send response
        m_Server.SendResponse(req.client_identity, req.request_id, response);
    }
}
```

**Why not ZMQ round-robin?**
- GET_NEXT can block for seconds waiting for new messages
- With round-robin, one slow request blocks all workers
- With queue, slow requests don't affect fast ones (PUBLISH, GET_CURRENT)
- `std::queue` + `std::mutex` is sufficient for network I/O (not CPU-bound)

## Behavior Differences from LocalMessageBroker

| Aspect | LocalMessageBroker | RemoteMessageBroker |
|--------|-------------------|---------------------|
| **Latency** | Microseconds | Milliseconds (network RTT) |
| **PrepareMessage (local)** | Returns pointer to shared memory | Returns pointer to shared memory |
| **PrepareMessage (remote)** | N/A | Allocates temporary heap buffer |
| **PublishMessage (local)** | Immediate (local) | Immediate (local) |
| **PublishMessage (remote)** | N/A | Blocking network call |
| **GetNextMessage** | Blocks on local event | Blocks on network response |
| **Subscribe** | Sets up event notification | No-op (GetNextMessage fetches) |
| **Frame IDs** | Sequential, contiguous | May have gaps (rate limited) |
| **Error handling** | Local exceptions | Network timeouts, retries |

## Use Cases

### Good Use Cases
- Remote displays at 10-60Hz
- Monitoring and diagnostics
- Low-frequency control commands
- Data logging from remote machines

### Poor Use Cases
- High-frequency streaming (2kHz)
- Real-time control loops
- Anything requiring sub-millisecond latency
- Large data transfers without rate limiting

## Configuration

```yaml
remote_broker:
  # This machine's identity
  machine_name: "machine1"

  # Server port for incoming requests
  server_port: 5001

  # Remote peers
  peers:
    - name: "machine2"
      host: "192.168.1.2"
      port: 5001
    - name: "raspberry-pi"
      host: "192.168.1.10"
      port: 5001

  # Timeouts
  # Note: Client has fixed 60s socket timeout, but server handles operation timeouts
  operation_timeout_ms: 5000    # Timeout for long operations (GetNextMessage)

  # Performance
  max_payload_size_mb: 10       # Reject messages larger than this
  enable_compression: false     # Optional payload compression
```

## Performance Characteristics

### Latency
- **Network RTT**: 0.5-2ms (local network)
- **GetNextMessage**: 1-3ms (including serialization)
- **PublishMessage**: 1-3ms (including serialization)

### Throughput
- **Max requests/second**: ~500-1000 (limited by latency)
- **Practical limit**: 10-60Hz per topic for remote access
- **Multiple topics**: Can handle multiple topics concurrently (one socket per peer)

### Bandwidth
- **Overhead**: ~100 bytes per request/response
- **Payload**: Raw data size
- **Total**: Request overhead + Payload + Response overhead

## Error Handling

### Timeout
The `Client` class has a default 60-second timeout. For operations with shorter timeouts (like `GetNextMessage`), the server handles the timeout and returns empty response:

```cpp
auto msg = broker.GetNextMessage("machine1/camera", ..., timeout=1.0);
if (!msg) {
    // Timeout - no message available within 1 second
    // Server returned empty response after waiting 1 second
}
```

### Connection Failure
- `Client::MakeRequest()` throws `std::runtime_error` on connection failure
- Socket reconnects automatically via Client's socket pooling
- `RemoteMessageBroker` catches exceptions and converts to appropriate return values (nullopt for GetNextMessage)

### Server Errors
Server returns `"ERROR"` status with error message:
```cpp
// In request handler
try {
    // ... operation ...
    return "OK";  // Success
} catch (const std::exception& e) {
    return std::string("ERROR: ") + e.what();
}
```

## Thread Safety

**Client-side (RemoteMessageBroker)**: Thread-safe. The `Client` class is already thread-safe (uses socket pooling with mutex), so `RemoteMessageBroker` operations can be called from multiple threads:

```cpp
// Safe to use from multiple threads
RemoteMessageBroker broker(local, config);

// Thread 1
auto msg1 = broker.GetNextMessage("machine1/topic1", ...);

// Thread 2
auto msg2 = broker.GetNextMessage("machine2/topic2", ...);
```

**Server-side (RemoteBrokerServer)**: Uses thread pool with `LocalMessageBroker`. Since `LocalMessageBroker` is fully thread-safe, multiple worker threads can call broker methods concurrently without additional synchronization.

**Why std::queue + mutex (not lock-free)?**
- Network I/O is not CPU-bound - mutex contention is negligible compared to network latency
- `std::queue` is simpler, easier to debug, and sufficient for this use case
- Lock-free queues are overkill for request rates under 1000/sec
- Focus complexity budget on reliability, not micro-optimizations

## Comparison with Original Async Design

| Feature | Async Design (Original) | Sync Design (Current) |
|---------|------------------------|----------------------|
| **Interface** | Separate from MessageBroker | Implements MessageBroker |
| **Paradigm** | Push-based (subscriptions) | Pull-based (requests) |
| **Sockets** | DEALER/ROUTER | REQ/REP |
| **Threads** | Multiple (TX, RX, Main) | None (blocking calls) |
| **Latency** | Sub-millisecond headers | 1-3ms per operation |
| **Bandwidth** | Optimized (subscriptions) | Request overhead per call |
| **Complexity** | High (state management) | Low (simple request/response) |
| **Use case** | High-frequency streaming | Displays, monitoring |
| **Scalability** | Good for many topics | Limited by request rate |

## Example Usage

```cpp
// Setup (running on machine1)
LocalMessageBroker local_broker(...);
RemoteMessageBroker broker(&local_broker, config);  // Handles both local and remote

// Publishing locally (fast - detects local machine from topic)
auto msg = broker.PrepareMessage("machine1/camera/stream", 1024);
// ... fill data ...
broker.PublishMessage(msg);  // Goes to local broker

// Publishing remotely (network round-trip)
auto msg2 = broker.PrepareMessage("machine2/command", 256);
// ... fill data ...
broker.PublishMessage(msg2);  // Blocks until remote ACK

// Subscribing to remote topic
auto sub = broker.Subscribe("machine2/telemetry",
                            MessageSubscriptionMode::NewestOnly);

// Getting messages (10Hz loop)
while (running) {
    auto msg = sub.GetNextMessage(0.1);  // 100ms timeout
    if (msg) {
        // Process message
        display.Update(msg.GetPayload());
    }
    std::this_thread::sleep_for(100ms);  // 10Hz
}
```

---

**Version:** 2.0  
**Last Updated:** 2026-02-09  
**Status:** Design Complete - Synchronous Model

## Implementation TODO

### Phase 1: Core Client/Server Infrastructure ✓ (COMPLETED)

- [x] **Create `RemoteMessageBroker` class skeleton**
  - Inherit from `MessageBroker`
  - Add member variables for `LocalMessageBroker*`, peer `Client` map, temp buffers
  - Implement constructor that creates `Client` objects for each peer

- [x] **Implement topic routing logic**
  - `IsLocalTopic()`: Check if topic starts with local machine name
  - `GetMachineFromTopic()`: Extract machine name from topic
  - `GetClientForMachine()`: Return reference to appropriate `Client`

- [x] **Implement `PrepareMessageImpl()`**
  - Local topics: Delegate to `LocalMessageBroker`
  - Remote topics: Allocate `std::vector<uint8_t>` temp buffer, return `Message` wrapper
  - Store temp buffer in `m_TempBuffers` map (keyed by topic)

- [x] **Implement `PublishMessage()`**
  - Local topics: Delegate to `LocalMessageBroker`
  - Remote topics: Serialize message, call `Client::MakeRequest("PUBLISH", data)`, free temp buffer on success

- [x] **Implement serialization helpers**
  - `SerializeMessage()`: Convert `Message` to string (header + payload)
  - `DeserializeMessage()`: Convert string back to `Message`
  - `SerializeGetNextRequest()`: Convert parameters to string

### Phase 2: Server Class Enhancement ✓ (COMPLETED)

**The `Server` class has been updated with built-in thread pool support:**

- [x] **Added thread pool to `Server` class**
  - Constructor: `Server(int port, int num_workers = 1)`
  - `ReceiveLoop()`: Receives from ZMQ, enqueues to `m_RequestQueue`
  - `WorkerLoop()`: Worker threads dequeue and process independently
  - `PendingRequest` struct for queue items
  - Uses `std::queue` + `std::mutex` + `std::condition_variable`

- [x] **Modified `Server` lifecycle**
  - `Start()`: Initializes ZMQ, launches receive thread + worker threads
  - `Stop()`: Signals shutdown, joins all threads, cleans up ZMQ
  - `SendResponse()`: Thread-safe method for workers to send replies

### Phase 2b: RemoteBrokerServer Implementation ✓ (COMPLETED)

- [x] **Create `RemoteBrokerServer` wrapper class**
  - Member variables: `MessageBroker*`, `Server`
  - Constructor: Create `Server` with desired number of workers, register all handlers
  - Start/Stop methods to control the server
  - Destructor cleans up

- [x] **Implement request handlers**
  - `HandlePublish()`: Deserialize message, call `PublishMessage()`, return "OK" or error
  - `HandleGetNext()`: Parse request params, call `GetNextMessage()` with timeout, serialize result (empty for timeout)
  - `HandleGetCurrent()`: Call `GetCurrentMessage()`, serialize result
  - `HandleGetRate()`: Call `GetMessageRate()`, return as string
  - `HandleListTopics()`: Call `GetAllMessageTopics()`, return comma-separated list

- [x] **Implement serialization/deserialization**
  - `SerializeMessage()`: Binary format [header_size][MessageHeader][payload]
  - `DeserializeMessage()`: Parse binary format, allocate heap memory for header/payload
  - `ParseGetNextRequest()`: Parse binary format for GET_NEXT parameters

### Phase 3: Message Subscription Support ✓ (COMPLETED)

- [x] **Implement `Subscribe()`**
  - Return `MessageSubscription` object
  - No-op for remote topics (GetNextMessage handles fetching)

- [x] **Implement `GetNextMessage()` and `TryGetNextMessage()`**
  - Local topics: Delegate to `LocalMessageBroker`
  - Remote topics: Serialize request, call `Client::MakeRequest()`, deserialize response
  - Handle timeouts correctly (server-side waits, client-side timeout)

- [x] **Implement `GetCurrentMessage()`**
  - Local topics: Delegate to `LocalMessageBroker`
  - Remote topics: Synchronous request/response

- [x] **Implement `GetAllMessageTopics()` and `GetMessageRate()`**
  - Local topics: Delegate to `LocalMessageBroker`
  - Remote topics: Synchronous request/response

### Phase 3b: Python Bindings ✓ (COMPLETED)

- [x] **Add Python bindings for `PeerConfig`**
  - Exposed as Python class with `name`, `host`, `port` attributes

- [x] **Add Python bindings for `RemoteBrokerServer`**
  - Constructor with broker, port, and num_workers parameters
  - `start()`, `stop()`, and `is_running` properties
  - Uses existing Server Python binding patterns

- [x] **Add Python bindings for `RemoteMessageBroker`**
  - Constructor with LocalMessageBroker, machine name, and peers list
  - `prepare_message()`, `publish_message()`, `publish_data()`, `publish_array()`
  - `try_get_message()`, `get_current_message()`, `is_message_available()`
  - `will_message_be_available()`, `get_newest_message_id()`, `get_oldest_message_id()`
  - `get_message_rate()`, `get_all_message_topics()`, `subscribe()`
  - Follows same patterns as LocalMessageBroker bindings

- [x] **Expose `MessageBroker` base class**
  - Required for proper inheritance chain in Python
  - Allows RemoteMessageBroker to properly inherit

### Phase 4: Testing

- [x] **Configuration structures** (Not needed - using existing patterns)
  - `PeerConfig` struct already exists (name, host, port)
  - Configuration passed directly to constructors, no YAML needed

- [x] **Create test file** (`tests/test_remote_message_broker.py`)
  - Test fixtures for LocalMessageBroker and RemoteMessageBroker
  - Test classes for TopicRouting, Serialization, RemoteBrokerServer, Concurrency, TimeoutHandling, SubscriptionModes, ErrorHandling

- [ ] **Fix failing tests**
  - **CRITICAL**: Segmentation fault in remote topic routing (message serialization issue)
    - Issue: `SerializeMessage` accesses `msg.m_Header` which appears valid but causes crash
    - Root cause: Likely memory corruption during Message construction/copy in PrepareMessageImpl
    - The Message object created with heap-allocated header is not being properly managed
  - **Fix needed**: Memory management in PrepareMessageImpl for remote topics
    - Current implementation uses `new MessageHeader()` but Message class expects shared memory
    - Need to ensure proper lifetime management of heap-allocated headers
  - **Alternative approach**: Instead of using PublishMessage for remote topics, directly serialize and send raw data without creating Message objects

- [ ] **Write integration tests** (after fixing unit tests)
  - Start two `RemoteBrokerServer` instances on different ports
  - Test publish/subscribe between them
  - Test concurrent access from multiple threads
  - Test timeout handling

### Phase 5: Error Handling and Edge Cases

- [ ] **Implement connection error handling**
  - Retry logic for failed connections
  - Graceful degradation when peer is offline
  - Clear error messages for network failures

- [ ] **Handle partial message failures**
  - Connection drops mid-request
  - Malformed requests/responses
  - Server-side exceptions in request handlers

- [ ] **Implement resource cleanup**
  - Destructor cleans up temp buffers
  - Stop thread pool gracefully
  - Close all Client connections

- [ ] **Add logging**
  - Log all remote operations (at DEBUG level)
  - Log connection events
  - Log errors with context

### Phase 6: Documentation and Polish

- [ ] **Update API documentation**
  - Document `RemoteMessageBroker` class
  - Document `RemoteBrokerServer` class
  - Add usage examples

- [ ] **Performance benchmarking**
  - Measure latency for different payload sizes
  - Measure throughput with multiple concurrent clients
  - Identify bottlenecks

- [ ] **Code review and cleanup**
  - Ensure consistent error handling
  - Check for memory leaks
  - Verify thread safety
  - Refactor if needed

## Testing Checklist

- [ ] Single machine: Local broker operations work as before
- [ ] Two machines: Can publish from machine1 and receive on machine2
- [ ] Multiple topics: Can subscribe to several remote topics simultaneously
- [ ] Concurrency: Multiple threads can call GetNextMessage on different topics
- [ ] Timeouts: GetNextMessage returns nullopt after specified timeout
- [ ] Error recovery: Server restart doesn't crash clients (they retry)
- [ ] Thread safety: No crashes or data races under heavy load
- [ ] Memory: No leaks detected with valgrind/ASAN

## Notes

- **Dependencies**: Existing `Client` and `Server` classes, `LocalMessageBroker`
- **Thread Safety**: `LocalMessageBroker` is thread-safe, so no additional locking needed in workers
- **Complexity**: Medium - mostly plumbing between existing components
- **Estimated Effort**: 2-3 weeks for experienced C++ developer
