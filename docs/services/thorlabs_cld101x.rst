Thorlabs Compact Laser Diode
============================

Controls a Thorlabs Compact Laser Diode (CLD) using ``pyvisa``. This service requires the VXIpnp VISA Instrument Driver to be
installed on the host system. The driver can be downloaded from the
`Thorlabs website <https://www.thorlabs.com/software_pages/viewsoftwarepage.cfm?code=4000_Series>`_ and is also included
on the CD that is shipped with the device.

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

``current_percent``: The current the laser diode is set to in percent of its maximum current.