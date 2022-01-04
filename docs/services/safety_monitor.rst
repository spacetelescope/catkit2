Safety Monitor
==============

This service periodically checks datastreams from other services and makes sure these are within specified bounds, and are not stale (were submitted within a certain timeframe before the check). Only the zeroth element of the datastream is checked. Each check interval, an update is submitted to the ``is_safe`` datastream.

Configuration
-------------

Example configuration:

.. code-block:: YAML

    safety:
      service_type: safety_monitor

      check_interval: 60  # seconds

      safeties:
        humidity_dm:
          service_name: omega_dm
          stream_name: humidity
          minimum_value: 1
          maximum_value: 28
          safe_interval: 60  # seconds
        temperature_dm:
          service_name: omega_dm
          stream_name: temperature
          minimum_value: 0
          maximum_value: 29
          safe_interval: 60  # seconds
        lab_ups:
          service_name: lab_ups
          stream_name: power_ok
          minimum_value: 0.5
          maximum_value: 1.5
          safe_interval: 60  # seconds

Properties
----------

``checked_safeties`` A list of safety names as described by the configuration file. The ``i``-th element indicates the safety of the ``i``-th element in the ``is_safe`` datastream.

Commands
----------
None.

Datastreams
-----------

``is_safe``: Whether the checked safety is safe or not. This datastream includes one element for each checked safety, with the ordering the same as the ``checked_safeties`` list property.
