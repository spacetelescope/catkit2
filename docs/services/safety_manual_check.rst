Safety Manual Check
===================

A service that allows the user to manually check the safety of the testbed through the ``safety_monitor`` service.

This service has a property called ``value`` whose initial value is read from the configuration file, and it can be set to any value by the user.
It is continuously submitted to the only datastream ``check``.

By setting the value to something new, the safety monitor picks up on the new value on the datastream ``check`` and it should react accordingly.

Configuration
-------------

.. code-block:: YAML

    safety_manual_check:
      service_type: safety_manual_check
      requires_safety: true

      dtype: int
      initial_value: 5

Properties
----------
``value``: The value that is continuously submitted to the datastream ``check``.


Commands
--------
None.

Datastreams
-----------
``check``: The data stream that is continuously checked for safety.