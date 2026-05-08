Thorlabs MCLS1
==============
Thorlabs MCLS1 service contains software for controlling the `Thorlabs MCLS1` laser source.
Backend selection is automatic at runtime:

- On Windows, the service uses the Thorlabs UART library backend.
- On non-Windows platforms (Linux/macOS), the service communicates directly over serial (pyserial).

On Windows, the environment variable ``CATKIT_THORLABS_UART_LIB_PATH`` must point to the Thorlabs UART library file used by this service.

Thorlabs software suite is publicly available at https://www.thorlabs.com/software-pages/mcls1/



Configuration
-------------

.. code-block:: YAML

    mcls1:
        service_type: thorlabs_mcls1
        simulated_service_type: thorlabs_mcls1_sim
        interface: thorlabs_mcls1
        requires_safety: false

        # Used by the Windows UART-library backend to find the device in the VCP list.
        vcp_port: 'VCP3'

        # Optional for non-Windows serial backend; if omitted, the service tries to
        # discover the port using vcp_port in the serial description/device name.
        # serial_port: '/dev/ttyUSB0'
        # baud_rate: 115200
        # serial_timeout: 1.0

        emission: 1
        current_setpoint: 100
        low_flux_current_setpoint: 35
        channel: 2
        target_temperature: 25

        channels:
            1: 640
            2: 670

Properties
----------

None.

Commands
---------

None.

Datastreams
-----------
``current_setpoint``: (mA) Output current level of the MCLS1 (in percent), used to set up the source. 

``emission``: (boolean/int) Source emission status. 0 is OFF, 1 is ON. Used to set up the source.

``target_temperature``: (Celsius) Target temperature of the MCLS1. Used to set up the cooling system.

``temperature``: (Celsius) Source temperature. Feedback only. 

``power``: (mW) Source output power. Feedback only. 