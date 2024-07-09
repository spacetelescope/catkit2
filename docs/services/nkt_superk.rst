NKT Super K Compact Tunable Laser
=================================
The NKT Super K service contains both the `NKT SuperK EVO Supercontinuum White Light Laser <https://contentnktphotonics.s3.eu-central-1.amazonaws.com/SuperK-EVO/SuperK%20EVO%20and%20EVO%20HP%20Product%20Guide-%2020231010%20R1.4.pdf>`_
and the `NKT SuperK VARIA Variable Bandpass Filter <https://contentnktphotonics.s3.eu-central-1.amazonaws.com/SuperK-VARIA/SuperK%20VARIA%20Product%20Guide-%2020231016%20R1.3.pdf>`_.



Configuration
-------------

.. code-block:: YAML

    nkt_superk:
        service_type: nkt_superk
        simulated_service_type: nkt_superk_sim
        interface: nkt_superk
        requires_safety: false

        port: COM4
        emission: 1
        power_setpoint: 100
        current_setpoint: 100
        nd_setpoint: 1.0
        lwp_setpoint: 633
        swp_setpoint: 643
        sleep_time_per_nm: 0.013
        base_sleep_time: 0.05

Properties
----------

Commands
--------

Datastreams
-----------
``base_temperature``: Base temperature output by the NKT EVO (Celsius).

``supply_voltage``: DC supply voltage to the NKT EVO.

``external_control_input``:

``emission``: Output emission

``power_setpoint``: Output emission power level (in percent)

``current_setpoint``:

``monitor_input``:

``nd_setpoint``:

``swp_setpoint``:

``lwp_setpoint``:

``nd_filter_moving``:

``swp_filter_moving``:

``lwp_filter_moving``:

