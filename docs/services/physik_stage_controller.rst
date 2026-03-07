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

.. code-block:: python

  # Example of using position properties
  # stage is the service instance for the Physik stage controller

  # Get
  x = stage.position_x # x is a float representing the current position of the x-axis (hardware query)
  y = stage.position_y # y is a float representing the current position of the y-axis (hardware query)

  # Set (triggers a move_to_wrapper call, which updates the target_positions datastream and commands the move)
  stage.position_x = 10.0
  stage.position_y = 20.0

Commands
--------
``move_to(positions)``: Move to absolute positions. ``positions`` is a dict mapping axis names to target positions (e.g., ``{'x': 1350.0, 'y': 1685.0}``).

.. code-block:: python

  # Example of using move_to by a command call
  # stage is the service instance for the Physik stage controller
  stage.move_to(positions={"x": 50.9, "y": 280.1})

``move_and_wait(positions)``: Move to absolute positions and wait until motion is complete. ``positions`` is a dict mapping axis names to target positions.

.. code-block:: python

  # Example of using move_and_wait by a command call
  # stage is the service instance for the Physik stage controller
  stage.move_and_wait(positions={"x": 192.0, "y": 37.5})

``move_relative(deltas)``: Move relative to current positions. ``deltas`` is a dict mapping axis names to relative movements (e.g., ``{'x': 10.0, 'y': -5.0}``).

.. code-block:: python

  # Example of using move_relative by a command call
  # stage is the service instance for the Physik stage controller
  stage.move_relative(deltas={"x": 9.0, "y": -3.0})

``move_relative_and_wait(deltas)``: Move relative to current positions and wait until motion is complete. ``deltas`` is a dict mapping axis names to relative movements.

.. code-block:: python

  # Example of using move_relative_and_wait by a command call
  # stage is the service instance for the Physik stage controller
  stage.move_relative_and_wait(deltas={"x": 10.0, "y": -5.0})

``get_positions()``: Get current positions of all axes as a dict.

.. code-block:: python

  # Example of using get_positions by a command call
  # stage is the service instance for the Physik stage controller
  pos = stage.get_positions()
  print(pos)  # e.g., {'x': 1350.0, 'y': 1685.0}

``stop_motion()``: Emergency stop all motion immediately.

.. code-block:: python

  # Example of using get_positions by a command call
  # stage is the service instance for the Physik stage controller
  stage.stop_motion()
  # Server Log:[physik_stage_controller] Motion stopped

Datastreams
-----------
``positions``: Current positions of all axes (float64 array, updated when motion is complete).

.. code-block:: python

  # Example of reading positions from the datastream
  # stage is the service instance for the Physik stage controller
  current_pos = stage.positions.get_latest_frame().data
  print(current_pos)  # e.g., [100. 122.5]

``target_positions``: Target positions when moves are commanded (float64 array). You can insert move commands into this datastream to command moves.

.. code-block:: python

  # Example of commanding a move by inserting into the datastream
  # stage is the service instance for the Physik stage controller
  target_move = np.array([newposx, newposy], dtype=np.float64)
  stage.target_positions.submit_data(target_move)

  # Example of reading target positions from the datastream
  current_pos = stage.target_positions.get_latest_frame().data
  print(current_pos)  # e.g., [20.8 23.]
