Thorlabs MCLS1
==============
Thorlabs MCLS1 service contains software for controlling the `Thorlabs MCLS1` laser source.
The communication is done through serial communication. 
Thorlabs software suite is publicly available at https://www.thorlabs.com/software-pages/mcls1/

.. note::

None.


Configuration
-------------

.. code-block:: YAML

    mcls1:
        service_type: thorlabs_mcls1
        simulated_service_type: thorlabs_mcls1_sim
        interface: thorlabs_mcls1
        requires_safety: false
        vcp_port: 'VCP3'

        emission: 1
        current_setpoint: 100
        low_flux_current_setpoint: 35
        channel: 2
        target_temperature: 25

        channels:
            1: 640
            2: 670

Properties
----------

None.

Commands
---------

None.

Datastreams
-----------
``current_setpoint``: (mA) Output current level of the MCLS1 (in percent), used to set up the source. 

``emission``: (boolean/int) Source emission status. 0 is OFF, 1 is ON. Used to set up the source.

``target_temperature``: (Celsius) Target temperature of the MCLS1. Used to set up the cooling system.

``temperature``: (Celsius) Source temperature. Feedback only. 

``power``: (mW) Source output power. Feedback only. 