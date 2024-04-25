Aim TTi PL-P Series Power Supply
================================
This service connects to an Aim TTi PL-P Series Power Supply. Manufacturer info can be found under: `https://www.aimtti.com/product-category/dc-power-supplies/aim-plseries <https://www.aimtti.com/product-category/dc-power-supplies/aim-plseries>`_

Note how: "The New PL-P Series is the programmable (remote control) version of the New PL Series [...]", since the above
website lists both variants (PL and PL-P).

The Python API used to control the device is `dcps <https://github.com/sgoadhouse/dcps>`_

Notes:

- The device automatically applies a remote interface lock when it is commanded for the first time
(see `manual <https://resources.aimtti.com/manuals/New_PL+PL-P_Series_Instruction_Manual-Iss18.pdf>`_, page 23).
This is also noted in the `dcps library <https://github.com/sgoadhouse/dcps/blob/afbe687236bfa6176240e26790dd26b6c395b515/dcps/AimTTiPLP.py#L85>`_.
Even after setting the interface lock to ``LOCAL``, this will instantly be overwritten back to ``REMOTE`` when a new command is issued.
- All remote commands are listed on page 34 of the `device manual <https://resources.aimtti.com/manuals/New_PL+PL-P_Series_Instruction_Manual-Iss18.pdf>`_.
- Only a minimum of the commands listed in the manual are implemented. More commands can easily be added in the future as needed.

The service has been successfully tested with the following device:
Aim TTi PL303QMD-P

Configuration
-------------

.. code-block:: YAML

    plp_power_source:
      service_type: aimtti_plp_device
      simulated_service_type: aimtti_plp_device_sim
      requires_safety: false

      visa_id: ASRL3::INSTR
      channels:
        flat_illuminator:
          channel_number: 1
          voltage: 23
          current: 0.120
        planet:
          channel_number: 2
          voltage: 0.0
          current: 0.0

Properties
----------
None.

Commands
--------
``query_commanded_voltage()``: Returns the voltage that is currently commanded on a channel (not the measured voltage).

``query_commanded_current()``: Returns the current that is currently commanded ona channel (not the measured current).

``set_over_voltage_protection()``: Sets the over voltage protection trip point for a channel.

``set_over_current_protection()``: Sets over current protection trip point for a channel.

``reset_trip_conditions()``: Attempts to clear all trip conditions on the device.

Datastreams
-----------
``voltage_commands[channel_name]``: The commanded voltage per channel, in V.

``current_commands[channel_name]``: The commanded current per channel, in A.

``measured_voltage[channel_name]``: The voltage measured on a device channel, in V.

``measured_current[channel_name]``: The current measured on a device channel, in A.
