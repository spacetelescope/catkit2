Thorlabs Power Meter
====================

This services periodically checks the measured power of a Thorlabs power meter.

Configuration
-------------

.. code-block:: YAML

    power_meter:
      service_type: thorlabs_pm
      simulated_service_type: thorlabs_pm_sim
      requires_safety: false

      serial_number: 111000222
      interval: 0.5

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
``power``: The measured power in W.

``dark``: The measured dark level in W.
