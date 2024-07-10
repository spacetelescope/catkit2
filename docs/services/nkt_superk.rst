NKT Super K Compact Tunable Laser
=================================
The NKT Super K service contains software for controlling both the `NKT SuperK EVO Supercontinuum White Light Laser <https://contentnktphotonics.s3.eu-central-1.amazonaws.com/SuperK-EVO/SuperK%20EVO%20and%20EVO%20HP%20Product%20Guide-%2020231010%20R1.4.pdf>`_
and the `NKT SuperK VARIA Variable Bandpass Filter <https://contentnktphotonics.s3.eu-central-1.amazonaws.com/SuperK-VARIA/SuperK%20VARIA%20Product%20Guide-%2020231016%20R1.3.pdf>`_.
This is done because a single open port to the device is needed that cannot be shared between multiple services.

Associated drivers for both the EVO and VARIA (found in the lined manuals) also need to be installed.

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
        nd_setpoint: 100
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
``base_temperature``: Base temperature output by the EVO (Celsius).

``supply_voltage``: DC supply voltage to the EVO.

``external_control_input``: Level of external feedback control for the EVO (Volts, DC).

``emission``: Output emission of the EVO (int) - 0 is OFF, 1 is ON.

``power_setpoint``: Output emission power level of the EVO (in percent).

``current_setpoint``: Output current level of the EVO (in percent).

``monitor_input``: Monitors the input to the VARIA from the EVO.

``nd_setpoint``: Set point for the VARIA ND filter.

``swp_setpoint``: Upper bandwidth limit for the VARIA (in nm).

``lwp_setpoint``: Lower bandwidth limit for the VARIA (in nm).

``nd_filter_moving``: Whether the ND filer is moving for the VARIA.

``swp_filter_moving``: Whether the short wavelength (high-pass) filter is moving for the VARIA.

``lwp_filter_moving``: Whether the long wavelength (low-pass) filter is moving for the VARIA.

