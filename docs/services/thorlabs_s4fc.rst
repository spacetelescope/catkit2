Thorlabs S4FC Fabry-Perot Laser Source
======================================

Thorlabs S4FC Fabry-Perot laser source service for power, emission, and temperature
control with power and temperature feedback streams.

Backend selection is automatic at runtime:

- On Windows, the service uses the Thorlabs UART library backend.
- On non-Windows platforms (Linux/macOS), the service communicates directly over serial (pyserial).

On Windows, the environment variable ``CATKIT_THORLABS_S4FC_UART_LIB_PATH`` must point to the
Thorlabs UART library file used by this service.

Configuration
-------------

.. code-block:: YAML

    thorlabs_s4fc:
        service_type: thorlabs_s4fc
        simulated_service_type: thorlabs_s4fc_sim
        interface: thorlabs_s4fc
        requires_safety: false

        # Used by the Windows UART-library backend to find the device in the VCP list.
        # Can be omitted if not on Windows.
        vcp_port: 'VCP3'

        # Required for non-Windows serial backend.
        serial_port: '/dev/ttyUSB0'
        serial_timeout: 1.0

        # Optional metadata for proxy users.
        center_wavelength: 637
        bandwidth: 20

        emission: 1
        power_setpoint: 70
        target_temperature: 25

Properties
----------

None.

Commands
--------

None.

Datastreams
-----------
``power_setpoint``: (mW) Output power setpoint.

``emission``: (boolean/int) Source emission status. 0 is OFF, 1 is ON.

``target_temperature``: (Celsius) Target source temperature.

``temperature``: (Celsius) Source temperature feedback.

``power``: (mW) Source output power feedback.

