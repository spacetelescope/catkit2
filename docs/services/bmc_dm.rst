Boston Deformable Mirror
========================

Configuration
-------------
.. code-block:: YAML

    boston_dm1:
        inclination:
          design: 0
          calibrated:
        clocking:
          design: 0
          calibrated:
        actuator_pitch: 150.0e-6
        num_actuators_across: 48
        reflective_diameter: 100.0e-3
        include_actuator_print_through: false
        max_volts: 200
        active_actuator_mask: !path "../data/boston/rst_dm_2Dmask.fits"
        actuator_influence_function: !path "../data/boston/boston_actuator_for_rst48.fits"
        actuator_print_through: !path "../data/boston/boston_mems_actuator_medres.fits"
        flat_map_voltage: !path "../data/boston/flat_map_volts_rst48.fits"
        meter_per_volt_map: !path "../data/boston/gain_map_rst48.fits"
        zero_padding_factor: 2  # 0 indicates no zero-padding.

Properties
----------

Commands
--------

Datastreams
-----------
