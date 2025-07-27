NKT Super K FIANIUM Compact Tunable Laser
=========================================
The NKT Super K service contains software for controlling both the `NKT SuperK FIANIUM Supercontinuum White Light Laser <https://www.nktphotonics.com/products/supercontinuum-white-light-lasers/superk-fianium/>`_
and the `NKT SuperK VARIA Variable Bandpass Filter <https://contentnktphotonics.s3.eu-central-1.amazonaws.com/SuperK-VARIA/SuperK%20VARIA%20Product%20Guide-%2020231016%20R1.3.pdf>`_.
This is done because a single open port to the device is needed that cannot be shared between multiple services.

Associated drivers for both the FIANIUM and VARIA also need to be installed.

.. note::
   There is a separate service for the NKT SuperK EVO.

Configuration
-------------

.. code-block:: YAML

    nkt_superk:
        service_type: nkt_superk_fianium
        simulated_service_type: nkt_superk_fianium_sim
        interface: nkt_superk_fianium
        requires_safety: false

        port: COM4
        pulse_picker_safety: 5

        emission: 3
        power_setpoint: 100
        pulse_picker_ratio: 1
        nd_setpoint: 100
        lwp_setpoint: 638
        swp_setpoint: 643
        sleep_time_per_nm: 0.013
        base_sleep_time: 0.05

Properties
----------

None.

Commands
--------

None.

Datastreams
-----------
``emission``: Output emission of the FIANIUM (int) - 0 is OFF, 3 is ON.

``power_setpoint``: Output emission power level of the FIANIUM (in percent).

``pulse_picker_ratio``: Pulse picker ratio for the FIANIUM.

``monitor_input``: Monitors the input to the VARIA from the FIANIUM.

``nd_setpoint``: Set point for the VARIA ND filter.

``swp_setpoint``: Upper bandwidth limit for the VARIA (in nm).

``lwp_setpoint``: Lower bandwidth limit for the VARIA (in nm).

``nd_filter_moving``: Whether the ND filer is moving for the VARIA.

``swp_filter_moving``: Whether the short wavelength (high-pass) filter is moving for the VARIA.

``lwp_filter_moving``: Whether the long wavelength (low-pass) filter is moving for the VARIA.
