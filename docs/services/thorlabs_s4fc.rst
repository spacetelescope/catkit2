Thorlabs S4FC Fabry-Perot Laser Source
======================================

Thorlabs S4FC Fabry-Perot laser source contains software for controlling the `Thorlabs S4FC` laser source.

Backend selection is automatic at runtime:

- On Windows, the service uses the Thorlabs UART library backend.
- On non-Windows platforms (Linux/macOS), the service communicates directly over serial (pyserial).

On Windows, the environment variable ``CATKIT_THORLABS_S4FC_UART_LIB_PATH`` must point to the
Thorlabs UART library file used by this service.

Thorlabs software suite is publicly available at https://www.thorlabs.com/software-pages/s4fc/


Configuration
-------------

.. code-block:: YAML

    thorlabs_s4fc:
        service_type: thorlabs_s4fc
        simulated_service_type: thorlabs_s4fc_sim
        interface: thorlabs_s4fc
        requires_safety: false

        # Used by the Windows UART-library backend to find the device.
        # Can be omitted if not on Windows.
        port: 'TPXXXXXXXX-XXXXX'

        # Optional for non-Windows serial backend.
        # serial_port: '/dev/ttyUSB0'
        # serial_timeout: 1.0

        emission: 1
        power_setpoint: 2
        low_flux_setpoint: 2
        target_temperature: 25

        bandwidth: 1
        center_wavelength: 637

Properties
----------

None.

Commands
--------
``get_enable()``: Return whether the hardware reports the source enabled. This is read from the device, independently of the ``emission`` datastream, and is not a measurement of optical power.

Proxy methods
-------------
``turn_on()`` submits the ON request, then polls ``get_enable()`` every 0.1 s until the hardware reports enabled. After a cold start this took about 5.5 s in one hardware test; it returns immediately if the source is already enabled. It raises ``TimeoutError`` if this does not happen within ``timeout`` (default 30 s) and does not retry or cycle emission. Do not change the power until it returns, as that can leave the source without optical output (issue #472). The wait does not prevent other clients from changing power concurrently. Also implements a ``wait_for_warmup`` argument that optionally waits 30s for the source to stabilize.``turn_off()`` disables emission without waiting.

Datastreams
-----------
``power_setpoint``: (mW) Output power.

``emission``: (boolean/int) Source emission status. 0 is OFF, 1 is ON. Used to set up the source.

``target_temperature``: (Celsius) Target temperature of the S4FC. Used to set up the cooling system.

``temperature``: (Celsius) Source temperature. Feedback only.

``laser_lock``: (boolean/int) Laser lock status. 0 is UNLOCKED, 1 is LOCKED.

