Omega Temperature Sensor
========================

This service operates an Omega ITHX-W3 temperature and humidity sensor. Both temperature and humidity are checked every ``time_interval``.

Configuration
-------------

.. code-block:: YAML

    omega_dm1:
      service_type: omega_ithx_w3
      simulated_service_type: omega_ithx_w3_sim

      ip_address: xxx.xxx.xxx.xxx
      time_interval: 30  # seconds

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
``temperature``: The temperature as measured by this sensor in Celsius.

``humidity``: The humidity as measured by this sensor in percent.
