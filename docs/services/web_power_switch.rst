Web Power Switch
================

This service controls a power switch that is controllable over the internet.

For some examples of commercially available web power switches:
https://controlbyweb.com/webswitch/
https://dlidirect.com/products/new-pro-switch


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
``{outlet_name}``: The name of an outlet added by the user using the add_outlet() command.
