Thorlabs Motorized Flip Mount
=============================

This service operates a `Thorlabs MFF101 <https://www.thorlabs.com/thorproduct.cfm?partnumber=MFF101>`_
motorized flip mount.

Configuration
-------------

.. code-block:: YAML

    beam_dump:
      service_type: thorlabs_mff101
      simulated_service_type: thorlabs_mff101_sim
      interface: flip_mount

      serial_number: 12345678
      positions:  # named positions resolved by the proxy.
        in_beam: 1
        out_of_beam: 2
        nominal: out_of_beam

Properties
----------
None.

Commands
--------
``blink_led()``: This blinks the LED on the front panel of the flip mount for a short period. This can be used to identify the right flip mount on the bench if required.

Datastreams
-----------
``current_position``: The current position of the flip mount. This can be set to either 1 or 2, indicating position 1 or 2. Other values will be silently ignored.

``commanded_position``: The commanded position of the flip mount. This can be set to either 1 or 2, indicating position 1 or 2. Other values will be silently ignored.
