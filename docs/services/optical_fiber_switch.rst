Optical Fiber Switch
====================

This service controls an optical fibers switch through a serial connection.

On a 2x2 switch, the input channel is either 1 or two, depending on whether the switch does a direct or crossed connection.

Configuration
-------------

.. code-block:: YAML

    optical_switch_8x1:
        service_type: optical_fiber_switch
        simulated_service_type: optical_fiber_switch_sim
        requires_safety: false

        port: 'COM5'
        baudrate: 9600

        min_channel: 1
        max_channel: 8

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
``input_channel``: The data stream being monitored for input channel changes. This is an int that sets the current input channel of the switch. Must be between the `min_channel` and `max_channel` defined in the configuration.

``current_input``: The current input channel of the switch.
