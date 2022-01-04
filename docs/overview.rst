Overview
========

Architecture
------------

Catkit2 operations in a client-server architecture, with all testbed operations being performed on separate processes to promote concurrent high-speed operations. A testbed server should be started before testbed operations can start. Catkit2 distinguishes between a "Service" and a "TestbedClient" (or "Client" for short). Both these processes connect to the testbed server, but in different ways.

A Service exposes an API (Application Programming Interface) for the server to call. A Service by itself cannot see other services or execute commands on them. They exclusively interact with the outside world through the server and their exposed API.

A Client on the other hand does not expose an API, but is able to access and execute the API of any Service (via the testbed server). Clients are able to see all running services on the server they are connected to, and communicate wit them via the server. All this communication is abstracted away from the user.

Service API specification
-------------------------

The API of a Service consists of three different types of objects, accessed via their name (a string). The three different types are described below:

Property
~~~~~~~~

This object provides (optionally) a setter and a getter. The data type can be anything that can be converted to JSON, so any simple values (integers, floats, strings), key-value pairs (dictionary) or list. This object mimics a Python property. An example of a property is the exposure time of a camera.

Command
~~~~~~~

This object can be called with named arguments (keywords in Python). Again, these arguments can be anything that can be converted to JSON. An example of a command is to start acquisition of a certain camera, or to blink the LED of a device on the testbed.

DataStream
~~~~~~~~~~

This object is a rolling buffer of fixed-size arrays. These arrays (or "DataFrame"s as they are called in catkit2) can be submitted to the data stream, at which point they are given a unique ID and appended to the end of the rolling buffer. DataStreams are located in shared memory, and are designed to be extremely fast. Data frames can be accessed directly as the underlying memory is shared between processes. No information is exchanged with the server during this. DataStreams provide the backbone of high-speed communication between services and clients in catkit2.

Data streams provide simultaneous access to data published by services. This allows for, for example, a camera to publish images on a data stream, which is then accessed by the main adaptive optics process, a process that performs some long-term post-processing on the data, a process that logs the taken images to disk and the graphical user interface, all running concurrently with little communication overhead.

Testbed clients can both read and write to a data stream. This allows for, for example, the adaptive optics process to write its deformable mirror (DM) commands to a data stream, which is the accessed by both the DM service to apply the shape on the DM, and a graphical user interface to provide feedback to the user.

Benchmarks for data streams can be found :ref:`here<benchmarks_data_streams>`.
