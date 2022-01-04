SNMP UPS
========

This services periodically checks a status value of a UPS operating under the SNMP protocol. Every ``check_interval`` a request is made to the UPS, and the resulting response is checked against known a known ``pass_status`` that indicates whether power is ok or not. The result of this check is submitted to the ``power_ok`` data stream.

Configuration
-------------

.. code-block:: YAML

    lab_ups:
      service_type: snmp_ups
      simulated_service_type: snmp_ups_sim

      ip_address: xxx.xxx.xxx.xx
      port: yyy
      snmp_oid: 1.2.3.4.5.6 # The OID of the UPS.
      community: string  # The community string of the UPS.
      pass_status: 64  # The status of a passing check.
      check_interval: 30  # seconds

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
``power_ok``: This indicates whether the UPS passed its power check or not. This is 1 if passing, and 0 if not passing.
