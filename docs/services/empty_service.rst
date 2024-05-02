Empty Service
=============

This service doesn't do anything, but is useful when you want to create a proxy-only service.

Configuration
-------------

.. code-block:: YAML

    light_source:
      service_type: empty_service
      interface: my_proxy
      requires_safety: false

      source_type: thorlabs_diode_group

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
None.
