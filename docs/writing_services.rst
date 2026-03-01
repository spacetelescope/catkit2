Writing Custom Services
=======================

This guide shows you how to write catkit2 services.

File Structure and Naming
-------------------------

An example file structure for your testbed is as follows:

    my_testbed/
    ├── services/
    │   ├── my_service.py          # service implementation
    │   ├── my_service_sim.py      # simulated service implementation
    ├── proxies/
    │   ├── my_service_proxy.py    # service proxy implementation
    ├── pyproject.toml             # entry-points for my_testbed

This file structure is not strict and you can put service and proxy implementations at any directory in your project. It is however recommended to separate the proxy implementation from the service implementation. This has two reasons. First, it helps to separate "server" from "client" code when writing them. Secondly, it allows you to not have to import hardware-related packages into your client-side code.

.. note::
    Each service is contained in a separate file. When catkit2 starts a service, it runs the source file directly rather than a class or function within that source file. This is done to support services written in C++ as well.

.. note::

   No matter where a service and/or proxy is defined, they need to be added to the entry points in the ``pyproject.toml`` file, so that they can be found by the testbed server and testbed proxy. We will do this later in this guide.

Service Class Implementation
----------------------------

Each service is implemented as a class. The name of the class can be arbitrary, but for consistency we recommend to use the same name as the service type in CamelCase. For example, if your service type is ``my_service``, then the service class would be named ``MyService``. The same applies to the simulated service, which would be named ``MyServiceSim`` in this case.

Each service class inherits from :class:`Service`, no matter whether it is a hardware service or simulated service. In actuality, simulated services are just regular services that have the same interface as the hardware service but emulate its behavior.

Any service proxy inherits from :class:`ServiceProxy`. This base class provides basic functionality to communicate with the service, so you don't have to write that yourself.

Communication Primitives
------------------------

Once started, services communicate with the outside world using the following primitives:

- **Properties**
  Configuration values that clients can read and optionally write.

- **Commands**
  Actions that clients can trigger on the service.

- **Data Streams**
  High-throughput streaming data (images, sensor readings).

- **Slots** (Experimental)
  A new unified primitive that combines Properties and Data Streams with type safety and automatic confirmation.

  .. warning::
    Slots are experimental and their API is subject to change. Use at your own risk.

These communication primitives are set up during the creation of your service and are the only way to interact with it once it is running. We will detail how to set up and use these communication primitives later on in this guide.

Minimal Service Example
-----------------------

Here is the simplest possible service:

.. code-block:: python

    from catkit2 import Service

    class EmptyService(Service):
        def __init__(self):
            super().__init__('empty_service')

        def open(self):
            pass

        def main(self):
            while not self.should_shut_down:
                self.sleep(1)

        def close(self):
            pass

    if __name__ == '__main__':
        service = EmptyService()
        service.run()

All services inherit from the ``Service`` base class. This base class provides base functionality and a ``run()`` method that you should call to run the service. This function will call the ``open()`` (optional), ``main()`` (mandatory) and ``close()`` (optional) in order. The ``run()`` method should be called at the end of your service file to allow the service to be started as in the above example.

Services follow a well-defined lifecycle:

1. **Initialization** - ``__init__()``. Calls ``super().__init__('empty_service')`` with the service type name. This function should be minimal, but you can check correctness of the config here. You should _not_ connect to any hardware during this function.
2. **Opening** - ``open()`` (optional). Create your properties, commands, data streams, and slots here. You should connect to your hardware here. At the end of this function, the service should be fully operational and able to accept requests from the outside world.
3. **Running** - ``main()`` (required). This is the main loop. After this loop ends, the service will shut down. Always regularly check ``self.should_shut_down`` which is a boolean variable that indicates whether the service is requested to shut down.
4. **Closing** - ``close()`` (optional). Clean up resources here. Even if ``main()`` raised an exception and ended unexpectedly, the ``close()`` function will get called. Essentially, this function acts like a ``finally`` block around your main function.

Note that even though ``open()`` and ``close()`` are optional, they were included in the above code example for completeness. Also note that ``self.sleep()`` was called in the above example. This is a replacement of ``time.sleep()`` that regularly checks ``self.should_shut_down`` and quits sleeping when it is ``True``. This improves responsiveness for shutting down the service and avoids potential deadlocks.

Registering Your Service
------------------------

For catkit2 to find your new Service type, you need to register it. To do this, add entry points to ``pyproject.toml``:

.. code-block:: toml

    [project.entry-points."catkit2.services"]
    my_service = "my_testbed.services.my_service"

    [project.entry-points."catkit2.proxies"]
    my_service_proxy = "my_testbed.proxies.my_service_proxy:MyServiceProxy"

Be sure to reinstall your package after each change for the changes to take effect.

.. note::
    The Service entry point contains the module / file where the service is implemented, but the service proxy entry point contains the class of the proxy itself.

Configuration
-------------

Now that your service type is registered, you can create a new service that uses it. Add the following to your ``services.yml`` configuration file:

.. code-block:: yaml

    new_service_id:
        service_type: new_service
        interface: new_service_proxy
        requires_safety: false

        serial_number: 83985734578
        update_interval: 1.0  # seconds
        timeout: 30  # seconds
        calibration:
            nm_per_step:
                x: 64
                y: 56
                z: 75

The ``new_service_id`` is the name of your new service. You'll be able to access your service using ``testbed.new_service_id`` afterwards, so choose a descriptive name for this.

There are several attributes afterwards:

- ``service_type`` (required) tells catkit2 what service implementation to start. This name should correspond to one of the entry points.
- ``interface`` (optional) tells catkit2 what service proxy type to use. If this is not given, a minimal service proxy will be used instead.
- ``simulated_service_type`` (optional) tells catkit2 what service implementation to start when the testbed is in simulated mode.
- ``requires_safety`` (required) indicates whether this service requires a safe testbed to operate. See :doc:`safety` for more information about the safety system.
- All further attributes are part of the configuration of the service, available via ``self.config`` while inside the service implementation. For example:

    .. code-block:: python

        def open(self):
            self.serial_number = self.config['serial_number']

            # Optional config with default
            self.timeout = self.config.get('timeout', 30)

            # Nested config
            self.nm_per_step_x = self.config['calibration']['x']

Defining Properties
-------------------

Properties expose service state to clients. They are ideal for configuration values and status.

Read-Only Property
^^^^^^^^^^^^^^^^^^

Use for status values that clients can read but not modify:

.. code-block:: python

    def open(self):
        self.make_property('sensor_id', self.get_sensor_id)

The first argument is the name of the property, the second is a function that gets called when your property value is requested by someone else.

Read/Write Property
^^^^^^^^^^^^^^^^^^^

Use for configuration values that clients can modify:

.. code-block:: python

    def open(self):
        self.make_property('exposure_time', self.get_exposure_time, self.set_exposure_time, type='float64')

    def get_exposure_time():
        return self._exposure_time

    def set_exposure_time(value):
        self.camera.set_exposure(value)

        self._exposure_time = value
        self.log.info(f'Exposure time set to {value}')

**Important**: The setter should validate the value and raise an exception if invalid. The exception will be propagated to the caller.

Note that we added a type here. Typed properties are faster but require a strict type. Available types: ``'int64'``, ``'float64'``.

Defining Commands
-----------------

Commands trigger actions on the service. They are ideal for operations that don't fit the property model. Commands should be quick: do not have a command ``calibrate()`` but use ``start_calibration()``. The reason for this is that the client will block until the command is completed and will accept no other command executions or property get/set requests while the current command is running.

Simple Commands
^^^^^^^^^^^^^^^

.. code-block:: python

    def open(self):
        self.make_command('start_acquisition', self.start_acquisition)
        self.make_command('reset', self.reset)

    def start_acquisition(self):
        self.log.info('Starting acquisition...')
        # Logic to start acquisition here. The actual acquisition
        # is done by the main() loop.

    def reset(self):
        self.log.info('Resetting device...')
        self._counter = 0

Commands with Arguments
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    def open(self):
        self.make_command('set_position', self.set_position)

    def set_position(self, x, y):
        self.log.info(f'Moving to position ({x}, {y})')
        self.stage.move_to(x, y)

Commands with Return Values
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    def open(self):
        self.make_command('get_status', self.get_status)

    def get_status(self):
        return {
            'temperature': self.read_temp(),
            'voltage': self.read_voltage(),
            'state': self.state
        }

Defining Data Streams
---------------------

Data streams enable high-performance data transfer for continuous data like images or sensor readings. Data streams operate in shared memory, allowing near-instant publishing and retrieval of data frames. However, they require strict typing and shape, set on creation. After creation, you can change the type and shape of the arrays, at a runtime cost. The preferred use-case is data that changes type/shape infrequently, such as camera images or DM commands.

Basic Data Stream
^^^^^^^^^^^^^^^^^

.. code-block:: python

    def open(self):
        # Create a 2D image stream (20 frame buffer)
        self.images = self.make_data_stream(
            'images',           # Stream name
            'float32',          # Data type
            [1024, 1024],       # Shape
            20                  # Buffer size (number of frames)
        )

    def main(self):
        while not self.should_shut_down:
            # Generate or acquire data
            image = self.acquire_image()

            # Submit to stream
            self.images.submit_data(image)

Data Types for Streams
^^^^^^^^^^^^^^^^^^^^^^

Common data types:

* ``'float32'``, ``'float64'`` - Floating point data
* ``'int8'``, ``'int16'``, ``'int32'``, ``'int64'`` - Signed integers
* ``'uint8'``, ``'uint16'``, ``'uint32'``, ``'uint64'`` - Unsigned integers

Reading from Data Streams (within a service)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Services can also read from their own data streams or from other services:

.. code-block:: python

    def main(self):
        # Subscribe to command stream from another service
        command_stream = self.testbed.other_service.command

        while not self.should_shut_down:
            try:
                # Wait for next frame (5 second timeout)
                frame = command_stream.get_next_frame(5)
                command = frame.data[0]

                # Process command
                self.process_command(command)

            except Exception:
                # Timeout of get_next_frame. We should check if we should shut down.
                continue

Defining Slots
--------------

.. warning::
   The Slots API is experimental and subject to change. Use at your own risk.

Slots are a new unified communication primitive that combines Properties and Data Streams into a single, type-safe API with confirmation.

Key Features:

* **Simpler types**: Slots are typed at creation (Json, Raw Bytes, Array).
* **Explicit about confirmation**: ``set()`` blocks until service confirms success while ``set_async()`` requests a change without confirmation.
* **Error Handling**: Clear exceptions for timeout, validation errors, cancellation
* **Unified API**: Single interface for all communication patterns rather than the unclear split between properties and data streams.

Creating Read-Only Slots
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from catkit2.catkit_bindings import SlotDataType

    def open(self):
        # Create read-only slots
        self.temperature_slot = self.make_json_slot('temperature')
        self.status_slot = self.make_raw_slot('status_bytes')
        self.image_slot = self.make_array_slot('camera_image')

Publishing Data to Slots
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    def main(self):
        while not self.should_shut_down:
            # Read sensor
            temp = self.read_temperature_sensor()

            # Publish to slot (type handled automatically)
            self.temperature_slot.publish(temp)

            # Capture image
            frame = self.capture_camera_frame()
            self.image_slot.publish(frame)

            self.sleep(0.1)

Creating Read-Write Slots
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    def open(self):
        # Create read-write slot with setter callback
        self.target_slot = self.make_json_slot(
            'target_temperature',
            self.on_set_target_temperature
        )

    def on_set_target_temperature(self, value, context):
        """Called when a client sets target_temperature."""
        # Check if cancelled.
        if context.is_cancelled():
            raise RuntimeError("Operation cancelled")

        # Check if `value` has the correct type.
        if not isinstance(value, float):
            raise RuntimeError("Value has the wrong type.")

        # Process the value
        self.target_temp = value

        # MUST confirm by publishing back
        context.publish_json(value)

In this example, the call to ``context.is_cancelled()`` is a bit superfluous, since the check is done right at the start of the call. However, this is more useful for set operations that take some time to do, such as motor movements. During those long tasks, you should regularly check ``context.is_cancelled()`` and cancel the operation if it is ``True``.

The setter callback is given a ``SlotContext`` object. This object provides the context of the request that was made. Its ``publish_*()`` methods will publish the current value on the correct topic with the correct ``trace_id``. You MUST call one of the ``publish_*()`` methods to confirm the set operation. If you don't, the client's ``set()`` call will timeout.

Accessing Services from Clients
-------------------------------

Getting a Service
^^^^^^^^^^^^^^^^^

.. code-block:: python

    from catkit2 import TestbedProxy

    testbed = TestbedProxy('127.0.0.1', 1234)
    service = testbed.temperature_controller

Using Properties (Client)
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Read property
    sensor_id = service.sensor_id

    # Write property
    service.exposure_time = 0.01

    # Handle errors
    try:
        service.exposure_time = 0.01
    except RuntimeError as e:
        print(f"Failed to set: {e}")

Using Commands (Client)
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Simple command
    service.calibrate()

    # Command with arguments
    service.set_position(x=100, y=200)

    # Command with return value
    status = service.get_status()
    print(f"Temperature: {status['temperature']}")

Using Data Streams (Client)
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Subscribe to stream
    subscription = service.images.subscribe()

    while running:
        try:
            frame = subscription.get_next_frame(timeout=1.0)
            image = frame.data
            process_image(image)
        except Exception:
            # Timeout or shutdown
            continue

Using Slots (Client - Experimental)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. warning::
   The Slots client API is experimental and subject to change.

Reading Data
^^^^^^^^^^^^

.. code-block:: python

    current = service.temperature.get()
    if current is not None:
        print(f"Temperature: {current}°C")

Setting Data
^^^^^^^^^^^^

**Synchronous (default)**: Blocks until service confirms

.. code-block:: python

    try:
        service.target_temperature.set(25.0, timeout=5.0)
    except SlotTimeoutError:
        print("Service didn't respond in time")
    except SlotSetterError as e:
        print(f"Service rejected: {e}")

**Asynchronous**: Returns immediately

.. code-block:: python

    trace_id = service.target_temperature.set_async(25.0)

Subscribing to Slot Updates
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    subscription = service.temperature.subscribe()

    while running:
        msg = subscription.get_next_message(timeout=1.0)
        if msg:
            data = msg.get_payload()
            print(f"New temperature: {data['temp']}")

Error Handling
--------------

Property Validation
^^^^^^^^^^^^^^^^^^^

Always validate property values and raise clear exceptions:

.. code-block:: python

    def set_exposure(self, value):
        if value <= 0:
            raise ValueError("Exposure must be positive")
        if value > 1000:
            raise ValueError("Exposure cannot exceed 1000ms")

        self.camera.set_exposure(value)

Slot Exceptions (Experimental)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from catkit2.catkit_bindings import (
        SlotTimeoutError,
        SlotSetterError,
        SlotCancelledError
    )

    try:
        service.config.set(value, timeout=2.0)
    except SlotTimeoutError:
        print("Timeout - service may be busy")
    except SlotSetterError as e:
        print(f"Setter error: {e}")
    except SlotCancelledError:
        print("Operation was cancelled")

Creating a Service Proxy
------------------------

Create a proxy class for convenient client access:

.. code-block:: python

    from catkit2.testbed.service_proxy import ServiceProxy

    class TemperatureControllerProxy(ServiceProxy):
        @property
        def temperature(self):
            """Get latest temperature reading."""
            frame = self.temperature.get_next_frame(0)
            return frame.data[0]

        def set_target(self, temp):
            """Set target temperature."""
            self.target_temperature = temp
