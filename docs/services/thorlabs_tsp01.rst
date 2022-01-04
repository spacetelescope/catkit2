Thorlabs Temperature Sensor
===========================

This service retrieves data from a Thorlabs TSP01B temperature and humidity sensor.

Configuration
-------------

Example configuration:

.. code-block:: YAML

    tsp01_1:
      service_type: thorlabs_tsp01
      simulated_service_type: thorlabs_tsp01_sim

      serial_number: M01234567
      num_averaging: 25  # optional
      interval: 60  # seconds between measurements, optional, default 10s

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
``temperature_internal``: The temperature of the sensor embedded inside the housing in Celsius.

``humidity_internal``: The humidity as measured by the sensor embedded inside the housing in percent.

``temperature_header_1``: The temperature of the external temperature probe connected to port 1 in Celsius.

``temperature_header_2``: The temperature of the external temperature probe connected to port 2 in Celsius.
