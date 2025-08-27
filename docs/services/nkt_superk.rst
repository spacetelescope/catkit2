NKT SuperK Compact Tunable Laser
=================================

The NKT SuperK services contain software for controlling NKT SuperK supercontinuum white light lasers
and the `NKT SuperK VARIA Variable Bandpass Filter <https://contentnktphotonics.s3.eu-central-1.amazonaws.com/SuperK-VARIA/SuperK%20VARIA%20Product%20Guide-%2020231016%20R1.3.pdf>`_.
This is done because a single open port to the device is needed that cannot be shared between multiple services.

Two service variants are available:

- **NKT SuperK EVO**: Controls the `NKT SuperK EVO Supercontinuum White Light Laser <https://contentnktphotonics.s3.eu-central-1.amazonaws.com/SuperK-EVO/SuperK%20EVO%20and%20EVO%20HP%20Product%20Guide-%2020231010%20R1.4.pdf>`_
- **NKT SuperK FIANIUM**: Controls the `NKT SuperK FIANIUM Supercontinuum White Light Laser <https://www.nktphotonics.com/products/supercontinuum-white-light-lasers/superk-fianium/>`_

Both services inherit from a common base class (``NktSuperkBase``) that provides shared functionality for VARIA filter control
and common device operations. Associated drivers for the laser and VARIA (found in the linked manuals) need to be installed.

Configuration
-------------

**NKT SuperK EVO Configuration:**

.. code-block:: YAML

    nkt_superk:
        service_type: nkt_superk_evo
        simulated_service_type: nkt_superk_evo_sim
        interface: nkt_superk_evo
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

**NKT SuperK FIANIUM Configuration:**

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

**Common VARIA Filter Datastreams (available in both EVO and FIANIUM):**

``monitor_input``: Monitors the input to the VARIA from the laser.

``nd_setpoint``: Set point for the VARIA ND filter.

``swp_setpoint``: Upper bandwidth limit for the VARIA (in nm).

``lwp_setpoint``: Lower bandwidth limit for the VARIA (in nm).

``nd_filter_moving``: Whether the ND filter is moving for the VARIA.

``swp_filter_moving``: Whether the short wavelength (high-pass) filter is moving for the VARIA.

``lwp_filter_moving``: Whether the long wavelength (low-pass) filter is moving for the VARIA.

**EVO-Specific Datastreams:**

``base_temperature``: Base temperature output by the EVO (Celsius).

``supply_voltage``: DC supply voltage to the EVO.

``external_control_input``: Level of external feedback control for the EVO (Volts, DC).

``emission``: Output emission of the EVO (int) - 0 is OFF, 1 is ON.

``power_setpoint``: Output emission power level of the EVO (in percent).

``current_setpoint``: Output current level of the EVO (in percent).

**FIANIUM-Specific Datastreams:**

``emission``: Output emission of the FIANIUM (int) - 0 is OFF, 3 is ON.

``power_setpoint``: Output emission power level of the FIANIUM (in percent).

``pulse_picker_ratio``: Pulse picker ratio for the FIANIUM.