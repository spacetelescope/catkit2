Thorlabs Cube Motors
====================

This service connects to Thorlabs TDC001 and Thorlabs KDC101 controllers in order to operate a motor.

This service uses bits of the official vendor Python library:
`https://github.com/Thorlabs/Motion_Control_Examples/tree/main/Python <https://github.com/Thorlabs/Motion_Control_Examples/tree/main/Python>`_
| The service also requires the installation of the Thorlabs Kinesis software:
`https://www.thorlabs.com/software_pages/viewsoftwarepage.cfm?code=Motion_Control# <https://www.thorlabs.com/software_pages/viewsoftwarepage.cfm?code=Motion_Control#>`_
| Then, to use Thorlabs cube motors with Kinesis, you need to set the ``THORLABS_KINESIS_DLL_PATH`` environment variable.

Successfully tested with the following devices:

- Thorlabs TDC001
- Thorlabs KDC101

Successfully tested with the motor stages:

- MTS25-Z8
- MTS50-Z8
- Z825B

Configuration
-------------

.. code-block:: YAML

    motor:
      service_type: thorlabs_cube_motor_kinesis
      simulated_service_type: thorlabs_cube_motor_kinesis_sim
      interface: thorlabs_cube_motor_kinesis

      cube_model: TDC001
      serial_number: 12345678
      stage_model: MTS50-Z8
      unit: mm
      min_position: 0.00
      max_position: 50.0

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

Datastreams
-----------
``command``: the current command sent to the motor.
``current_position``: the current (commanded) position of the motor.