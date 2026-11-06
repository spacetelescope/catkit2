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

None.

Datastreams
-----------
``power_setpoint``: (mW) Output power.

``emission``: (boolean/int) Source emission status. 0 is OFF, 1 is ON. Used to set up the source.

``target_temperature``: (Celsius) Target temperature of the S4FC. Used to set up the cooling system.

``temperature``: (Celsius) Source temperature. Feedback only.

``laser_lock``: (boolean/int) Laser lock status. 0 is UNLOCKED, 1 is LOCKED.

