Physik Instrumente Stage Controller
=====================================

This service controls Physik Instrumente (PI) motion stages using the `pipython` library. It has been tested with:

- E-727.3SDA controller with S-330.2SH stages

For controller specs, see the PI website.
Note that using PI controllers requires manual installation of the GCS DLL drivers from `physikinstrumente.com <https://www.physikinstrumente.com/en/products/controllers-and-drivers/>`_

Configuration
-------------

.. code-block:: YAML

    physik_stage_controller:
      service_type: physik_stage_controller
      simulated_service_type: physik_stage_controller_sim
      requires_safety: false
      
      controller_name: 'E-727.3SDA'
      stages: 'S-330.2SH'
      refmodes: 'FNL'
      SN: '123456'
      
      axis_map:
        x: 1
        y: 2
      
      initial_position:
        x: 1350
        y: 1685

Properties
----------
``position_{axis_name}``: Get or set the position for each configured axis (e.g., ``position_x``, ``position_y``).

Commands
--------
``move_to(positions)``: Move to absolute positions. ``positions`` is a dict mapping axis names to target positions (e.g., ``{'x': 1350.0, 'y': 1685.0}``).

``move_and_wait(positions)``: Move to absolute positions and wait until motion is complete. ``positions`` is a dict mapping axis names to target positions.

``move_relative(deltas)``: Move relative to current positions. ``deltas`` is a dict mapping axis names to relative movements (e.g., ``{'x': 10.0, 'y': -5.0}``).

``move_relative_and_wait(deltas)``: Move relative to current positions and wait until motion is complete. ``deltas`` is a dict mapping axis names to relative movements.

``get_positions()``: Get current positions of all axes as a dict.

``stop_motion()``: Emergency stop all motion immediately.

Datastreams
-----------
``positions``: Current positions of all axes (float64 array, updated when motion is complete).

``target_positions``: Target positions when moves are commanded (float64 array). You can insert move commands into this datastream to command moves.

``is_moving`` (sim only): Whether any axis is currently in motion (int8).
