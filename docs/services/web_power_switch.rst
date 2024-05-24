Web Power Switch
================

This service controls a power switch that is controllable over the internet.

So far catkit2 has been tested on the following web power switches:

- `LPC7-PRO from TeleDynamics <https://www.teledynamics.com/#/productdetails/LPC7-PRO>`_

Configuration
-------------

.. code-block:: YAML

    web_power_switch1:
        service_type: web_power_switch
        simulated_service_type: web_power_switch_sim
        interface: web_power_switch
        requires_safety: false

        user: username
        password: password
        ip_address: 000.000.000.00
        dns: domain_name_system

        # Plugged-in devices with their outlet number:
        outlets:
            npoint_tiptilt_lc_400: 1
            iris_usb_hub: 2
            newport_xps_q8: 3
            iris_dm: 4
            quad_cell: 5
            air_valve: 6
            pupil_led: 7
            fpm_led: 8

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
``{outlet_name}``: The name of an outlet. These are defined by the config file (see the sample Configuration section above where the names of eight example outlets are given).
