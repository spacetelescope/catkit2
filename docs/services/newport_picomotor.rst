Newport Picomotor
=================

This service controls a Newport Picomotor Motion Controller (see link below for an example of one that has been used with catkit2).

https://www.newport.com/f/open-loop-picomotor-motion-controller

The bottom of the webpage linked above has resources for the user including software downloads, technical notes, and user manuals.

Configuration
-------------

.. code-block:: YAML

    picomotor1:
        service_type: newport_picomotor
        simulated_service_type: newport_picomotor_sim
        interface: newport_picomotor
        requires_safety: false

        ip_address: 000.000.000.000
        max_step: 2147483647
        timeout: 60
        atol: 1
        daisy: 0  # use this when daisy chaining multiple picomotor controllers
        axes:
            x: 1
            y: 2
            z: 3
        sleep_per_step: 0.0005  # sleep time (s) between every step
        sleep_base: 0.1  # base sleep time (s) for every move command

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
``{axis_name}_command``: A movement command along the axis corresponding to axis_name (where axis_name can be x, y, or z).

``{axis_name}_current_position``: The current position of the picomotor along the axis corresponding to axis_name (where axis_name can be x, y, or z).
