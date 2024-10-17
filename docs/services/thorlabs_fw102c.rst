Thorlabs Filter Wheel
=====================
This service operates a Thorlabs filter wheel.

Successfully tested with the following devices:

- `ThorLabs FW 102C <https://www.thorlabs.com/thorproduct.cfm?partnumber=FW102C#ad-image-0>`_

Configuration
-------------
.. code-block:: YAML

    filter_wheel:
        service_type: thorlabs_fw102c
        simulated_service_type: thorlabs_fw102c_sim
        requires_safety: false

        visa_id: ASRL6::INSTR

        filters:
          clear: 1
          2.8_percent: 2
          12_percent: 3
          9_percent: 4

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
``position``: The commanded position of the filter wheel. This can have value 1, 2, 3, 4, 5, 6 indicating those respective positions.

``current_position``: The current position of the filter wheel. This can have value 1, 2, 3, 4, 5, 6 indicating those respective positions.