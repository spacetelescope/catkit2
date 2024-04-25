Thorlabs Compact Laser Diode
============================

Controls a Thorlabs Compact Laser Diode (CLD) using ``pyvisa``.

Successfully tested with the following devices:
- Thorlabs CLD1010LP
- Thorlabs CLD1011
- Thorlabs CLD1015

Configuration
-------------

.. code-block:: YAML

    thorlabs_laser_diode_1:
      service_type: thorlabs_cld101x
      simulated_service_type: thorlabs_cld101x_sim
      requires_safety: false

      visa_id: USB::0x1313::0x804F::M00441199::INSTR
      wavelength: 640

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
``current_setpoint``: The current the laser diode is set to in A.

``current_percent`: The current the laser diode is set to in percent of its maximum current.