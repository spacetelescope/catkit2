Thorlabs Cube Motors
====================

This service connects to Thorlabs TDC001 and Thorlabs KDC101 controllers in order to operate a motor.

The Python API used to control the device is https://github.com/qpit/thorlabs_apt

Successfully tested with the following devices:

- Thorlabs TDC001
- Thorlabs KDC101

Configuration
-------------

.. code-block:: YAML

    motor:
      service_type: thorlabs_cube_motor
      simulated_service_type: thorlabs_cube_motor_sim
      interface: thorlabs_cube_motor

      serial_number: 12345678
      positions:  # named positions resolved by the proxy.
        nominal: arbitrary_2
        arbitrary_1: 10
        arbitrary_2: 25

Properties
----------
None.

Commands
--------
``home()``: This will home the motor and block until the motor has finished homing.
``stop()``: This will stop any current movement of the motor.
``is_in_motion()``: This will check if the motor is currently moving.

Datastreams
-----------
``command``: the current command sent to the motor.
``current_position``: the current (commanded) position of the motor.