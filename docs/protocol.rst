Communication Protocol
======================

This page describes the communication protocol used between the testbed, services, and experiments.

Catkit2 uses a standard request-reply client-server model for communication. In Catkit2, each Service acts as a server, and any connecting entity acts as a client. Both the Testbed and each Service run a server. The Testbed server's port number is specified in the configuration file, while Services start their servers on random ports. The Testbed server maintains a registry of each Service's port number. To connect to a Service, a ServiceProxy first contacts the Testbed to retrieve the Service's current port number, then connects directly to the Service.

All communication occurs over TCP using ZeroMQ sockets with the REQ-REP pattern. For the remainder of this section, we use the terms "Server" and "Client" (referencing the C++ classes ``Server`` and ``Client``), but you can substitute Service and ServiceProxy, which fulfill those roles.

Request-Reply Flow
------------------

A typical server-client exchange follows this pattern:

1. **Client sends request:** The request consists of two parts:
   
   * A string indicating the request type (e.g., ``set_property_request``)
   * Request data serialized using Protocol Buffers (e.g., property name and new value)

2. **Server receives request:** The server looks up the appropriate request handler in its registry.

3. **Server processes request:** The handler deserializes the Protocol Buffer data, performs the requested action, and returns response data (again serialized with Protocol Buffers) if successful. If an error occurs, the handler raises an exception, which the server captures before sending the reply.

4. **Server sends reply:** The reply contains two parts:
   
   * A status indicator (``OK`` or ``ERROR``)
   * Either the response data or an error message

5. **Client processes reply:** If the request failed, the client raises an error with the server's error message. Otherwise, the response data is returned.

Implementation Details
----------------------

Single-Threaded Request Handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Servers use a single worker thread for request handling. This design choice simplifies data access patterns and establishes clear expectations for multithreading when setting properties. However, this single-threaded approach means that long-running request handlers will block the server from responding to new requests. Therefore, avoid long-running operations in request handlers.

For example, instead of implementing ``run_wavefront_control(num_iterations)`` as a blocking command that runs multiple iterations, implement it as ``start_wavefront_control(num_iterations)``, which initiates the wavefront control loop on the Service's main thread. This approach may require adjustment for those unfamiliar with asynchronous programming patterns.

Socket Pooling
~~~~~~~~~~~~~~

The client maintains a pool of reusable sockets. When ``client->MakeRequest()`` is called, a socket is retrieved from the pool to send the message to the server. If the pool is empty, a new socket is created (which may incur a small connection overhead). After the request completes, the socket is automatically returned to the pool.

This design prevents request interleaving, as each ZeroMQ client socket handles only one request at a time. If the server fails to respond within a specified timeout, the request is considered lost, and any subsequent reply from the server is ignored. ZeroMQ handles this internally using the ``ZMQ_CORRELATE`` option, which uses request identifiers to match replies with their corresponding requests.
