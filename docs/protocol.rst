Communication protocol
======================

This page provides details about the underlying communication protocol used to communcate between the server, clients and services. All this communication is abstracted away from the user, so unless you are interested in the internals, or need to work on it, there is no need to read this.

Server
------

Sockets
~~~~~~~

Communication is performed using ZeroMQ sockets. Any communication that uses the server is not deemed time-critical, so no effort was made to minimize latency. Despite this, communication is reasonably fast, being around a millisecond for a request to go through the chain of  client->server->service->server->client, just not useful for real-time processing of camera images or other tasks requiring sub-millisecond end-to-end response time.

The main communcation pattern is based on the `Majordomo protocol <https://rfc.zeromq.org/spec/7/>`_, but simplifies in a few areas. The server only has a single ROUTER socket, which binds to a port on localhost, specified by the configuration. Both Services and Clients connect to this socket. Services use a DEALER socket to handle asynchronous messages (ie. heartbeating). Clients use a REQ socket, to ensure that we get a reply for every request that we send to the server.

Additionally, the server has a PULL and a PUB socket, both of which bind to separate ports on local host. The PULL socket collects log messages from all services, and rebroadcasts them on the PUB socket. Anyone can listen with a SUB socket to the PUB socket to receive all log messages related to this testbed server.

Services send periodic heartbeats to the server and vice versa. This is part of the safety system of catkit2. Services that have not received a heartbeat from the server in a specified time, will assume that the server crashed and will automatically and safely shut down themselves at that point.

Wire protocol
~~~~~~~~~~~~~

Incoming messages:

.. code-block:: text

    Frame -1: <source identity (automatically added when receiving with the ROUTER socket of the server)
    Frame 0: empty (automatically added when sending from the REQ socket of a client)
    Frame 1: <message_source> (SERVICE or CLIENT)
    Frame 2: <service_name>
    Frame 3: <message_type>
    Frame 4&5: <data specific to message type> (may be omitted for some types)

Outgoing messages:

.. code-block:: text

    Frame -1: <source identity> (for the ROUTER socket to know where to send the message)
    Frame 0: empty (required for correct receiving by the REQ socket).
    Frame 1: REQUEST or REPLY or CONFIGURATION or HEARTBEAT
    Frame 2+: <data specific to message type> (may be omitted for some types)

Client
------

The protocol for the client is pretty clean. It only supports sending requests to a server, and only receives replies from that server, corresponding to the request that was sent.

Wire protocol
~~~~~~~~~~~~~

Outgoing messages:

.. code-block:: text

    Frame 0: empty (automatically added by REQ socket)
    Frame 1: <message source> (CLIENT)
    Frame 2: <service name>
    Frame 3: REQUEST
    Frame 4: <json request>

Incoming messages:

.. code-block:: text

    Frame 0: empty (required for REQ socket)
    Frame 1: REPLY
    Frame 2: <json reply>

Service
-------

Services receive requests, a configuration file and heartbeats from the server. It responds to requests by sending replies. It also sends an opened message as part of the initial handshake. Finally it periodically sends heartbeats to the server, to let it know the service is still alive.

Wire protocol
~~~~~~~~~~~~~

Outgoing messages:

.. code-block:: text

    Frame 0: empty
    Frame 1: <message source> (SERVICE)
    Frame 2: <service name>
    Frame 3: REGISTER or OPENED or HEARTBEAT or REPLY

    HEARTBEAT:
    No other frames.

    OPENED:
    No other frames.

    REGISTER:
    Frame 4: <json registration>

    REPLY:
    Frame 4: <client identity>
    Frame 5: <json reply>

Incoming messages:

.. code-block:: text

    Frame 0: empty
    Frame 1: REQUEST or HEARTBEAT or CONFIGURATION

    HEARTBEAT:
    No other frames.

    CONFIGURATION:
    Frame 2: <json configuration>

    REQUEST:
    Frame 2: <client identity>
    Frame 3: <json request>
