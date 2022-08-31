Overview
========

Architecture
------------

Catkit2 uses a service-oriented architecture to operate the testbed. A Service can operate a hardware device, or perform more complex operations with other services such as control loops or safety mechanisms. Each service runs on a separate process to promote concurrent high-speed operations, and exposes an API to the outside world using either a slow server-client protocol, used for setting and getting parameters or execute methods, or a high-speed low-latency data stream, for example used for sharing camera images or deformable mirror commands. Services are managed by the Testbed. The Testbed can start and stop services, manages configuration files and provides service discovery to allow scripts and other services to find services.

Communication with the Testbed and Services are handled using proxy objects, available from both C++ and Python. These seamlessly proxy any setting and getting of properties, executing methods or accessing data streams to the required process. All explicit communication is hidden from the user.

Service API specification
-------------------------

The API of a Service consists of three different types of objects, accessed via their name (a string). The three different types are described below:

Property
~~~~~~~~

This object provides (optionally) a setter and a getter. The data type can be either a None, an integer, a floating point number, a string, a boolean or an N-dimensional array, or any nested list or dictionary combination of these. An example of a property is the exposure time or the region of interest of a camera. In C++ accessing properties is done via `service->GetProperty("exposure_time")` and `service->SetProperty("exposure_time", 100)`. In Python, properties are converted into Python properties and can be accessed as an attribute as `service.exposure_time = 100`.

Command
~~~~~~~

Commands can be called with named arguments (keyword arguments in Python). Again, these arguments can be either None, an integer, a floating point number, a string, a boolean or an N-dimensional array, or any nested list or dictionary combination of these. An example of a command is to start acquisition of a certain camera, or to blink the LED of a device on the testbed.

DataStream
~~~~~~~~~~

This object is a rolling buffer of fixed-size arrays. These arrays (or "DataFrame"s as they are called in catkit2) can be submitted to the data stream, at which point they are given a unique ID and appended to the end of the rolling buffer. DataStreams are located in shared memory, and are designed to be extremely fast. Data frames can be accessed directly as the underlying memory is shared between processes. No information is exchanged with the server during this. DataStreams provide the backbone of high-speed communication between services and clients in catkit2.

Data streams provide simultaneous access to data published by services. This allows for, for example, a camera to publish images on a data stream, which is then accessed by the main adaptive optics process, a process that performs some long-term post-processing on the data, a process that logs the taken images to disk and the graphical user interface, all running concurrently with little communication overhead.

Testbed clients can both read and write to a data stream. This allows for, for example, the adaptive optics process to write its deformable mirror (DM) commands to a data stream, which is the accessed by both the DM service to apply the shape on the DM, and a graphical user interface to provide feedback to the user.

Benchmarks for data streams can be found :ref:`here<benchmarks_data_streams>`.
