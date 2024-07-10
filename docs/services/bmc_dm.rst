Boston Deformable Mirror
========================
This service operates a pair of identical Boston Micromachines MEMS DMs controlled by the same driver. The following Boston DMs have been tested with catkit2 thus far:

- `BMC DM Kilo-C-1.5 <https://bostonmicromachines.com/products/deformable-mirrors/standard-deformable-mirrors/>`_

Configuration
-------------
.. code-block:: YAML

    boston_dm:
        service_type: bmc_dm
        simulated_service_type: bmc_dm_sim
        interface: bmc_dm
        requires_safety: true

        serial_number: 0000
        command_length: 2048
        num_actuators: 952
        dac_bit_depth: 14
        max_volts: 200

        flat_map_fname: !path ../flat_data.fits
        gain_map_fname: !path ../gain_map.fits
        dm_mask_fname: !path ../dm_mask.fits

    startup_maps:
        flat: !path ../flat_data.fits

    channels:
        - correction_howfs
        - correction_lowfs
        - probe
        - poke
        - aberration
        - atmosphere
        - astrogrid
        - resume
        - flat

Properties
----------
``channels``: List of command channel names (dict).

Commands
--------

None.

Datastreams
-----------
``total_voltage``: Map of the total voltage applied to each actuator of the DM.

``total_surface``: Map of the total amplitude of each DM actuator (meters).

``channels[channel_name]``: The command per virtual channel, identified by channel name.
