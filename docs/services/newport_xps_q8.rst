Newport Motor Controller
========================

This service controls a Newport XPS motor controller which controls a set of motors identified by their motor IDs. These motor
names are defined in the configuration file and have to follow the naming given to them through the Newport control interface.

Each motor can define an arbitrary number of named positions. These named positions can can also call each other in a chain. This
is useful for being able to save motor positions associated with different experiment modes.

Configuration
-------------

.. code-block:: YAML

    newport_xps:
      service_type: newport_xps_q8
      interface: newport_xps_q8
      simulated_service_type: newport_xps_q8_sim
      requires_safety: false

      ip_address: xxx.xxx.xxx.xxx
      port: 0000
      timeout: 20
      update_interval: 1
      atol:
        default: 0.001
        lyot_theta: 0.01

      # Any update to the values below might require an update in simulator.yml.
      # Any difference with the values in simulator.yml will cause a misalignment between your hardware and the simulator.
      motors:

        example_motor:
          nominal: in_beam

          in_beam: in_beam_mode2
          on_axis: on_axis_mode2
          out_of_beam: out_of_beam_mode2
          lowfs_beam: lowfs_beam_mode2

          in_beam_mode1: 7.951
          on_axis_mode1: 7.871
          out_of_beam_mode1: 5.9
          lowfs_beam_mode1: 10

          in_beam_mode2: 9.301
          on_axis_mode2: in_beam_mode2
          out_of_beam_mode2: 8
          lowfs_beam_mode2: in_beam_mode2

        Lyot_X:
          nominal: 8.27
        Lyot_Y:
          nominal: in_beam
          in_beam: 2.3
          out_of_beam: 20
        Lyot_Z:
          nominal: 9.7
        Lyot_theta:
          nominal: 56
        camera_position:
          nominal: 5.42

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
``{motor_name}_command``: A movement command for the motor identified with motor_name. The motor names are defined by the config file.

``{motor_name}_current_position``: The current position of the motor identified with motor_name. The motor names are defined by the config file.