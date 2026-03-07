Overview
========

Architecture
------------

Catkit2 uses a service-oriented architecture to operate testbeds. A Service can operate a hardware device or perform complex operations using other services, such as control loops or safety mechanisms. Each service runs in a separate process to enable high-speed concurrent operations and exposes an API for external communication. This API supports setting and getting parameters, executing methods (such as setting camera exposure time or starting acquisition), and high-speed, low-latency data sharing (such as camera images or deformable mirror commands).

Services are managed by a Testbed object, which can start and stop services, manage configuration files, and provide service discovery. This allows scripts and other services to locate and interact with each other.

Communication with the Testbed and Services is handled using proxy objects, available in both C++ and Python. These proxies seamlessly handle property access, method execution, and data stream operations across processes, hiding all communication details from the user.

Service API Specification
-------------------------

Each Service API consists of three types of objects, accessed by name (a string):

Properties
~~~~~~~~~~

Properties provide optional getter and setter functionality. Supported data types include:

* None
* Integers
* Floating-point numbers
* Strings
* Booleans
* N-dimensional arrays
* Nested combinations of the above types

Examples of properties include camera exposure time and region of interest.

**C++:**

.. code-block:: cpp

    service->GetProperty("exposure_time")
    service->SetProperty("exposure_time", 100)

**Python:**

Properties are mapped to Python attributes for intuitive access:

.. code-block:: python

    service.exposure_time = 100

Commands
~~~~~~~~

Commands are callable methods that accept named arguments. Like properties, command arguments support the same data types (integers, floats, strings, booleans, arrays, and nested structures).

Examples include starting camera acquisition or blinking a device LED.

Data Streams
~~~~~~~~~~~~

Data Streams are rolling buffers of fixed-size arrays called DataFrames. When data is submitted to a stream, it receives a unique ID and is appended to the buffer. Data Streams reside in shared memory and are designed for extremely fast access, achieving single-digit microsecond latencies.

Since Data Streams use shared memory, data can be accessed directly across processes without involving the Testbed server, enabling efficient high-speed communication between services and their proxies.

Key features of Data Streams:

* **Simultaneous access:** Multiple processes can read from a single Data Stream concurrently. For example, a camera can publish images that are simultaneously consumed by:
  
  * An adaptive optics process
  * A long-term post-processing pipeline
  * A logging process for disk storage
  * A graphical user interface

* **Concurrent read/write:** Any number of readers and writers can access a Data Stream simultaneously. For instance, an adaptive optics process can write deformable mirror (DM) commands to a stream, which are then read by both the DM service (to apply the shape) and a GUI (to provide user feedback).

All processes run concurrently with minimal communication overhead.

See :ref:`benchmarks_data_streams` for performance measurements.
