Hamamatsu Camera
====================

This service controls a Hamamatsu camera. It is a wrapper around the DCAM SDK, which is distributed on the manufacturer
website together with their Python API ``dcam``:
`https://www.hamamatsu.com/eu/en/product/cameras/software/driver-software.html <https://www.hamamatsu.com/eu/en/product/cameras/software/driver-software.html>`_

The service requires the definition of an environment variable ``CATKIT_DCAM_SDK_PATH`` that points to the
``python`` directory within the DCAM SDK installation.

The service has been successfully tested with the following camera models:

- Hamamatsu ORCA-Quest C15550-20UP
- Hamamatsu ORCA-Quest 2 C15550-22UP

Configuration
-------------

In addition to the base camera configuration, the following Hamamatsu-specific options are available:

.. code-block:: YAML

    camera1:
        service_type: hamamatsu_camera
        simulated_service_type: camera_sim
        requires_safety: false

        camera_id: 0
        cooling_mode: 'on'
        fan_status: 'off'
        camera_mode: 'ultraquiet'
        pixel_format: Mono16
        binning: 1
        critical_temperature: 28

        # Base camera configuration
        width: 400
        height: 400
        offset_x: 0
        offset_y: 0
        exposure_time: 8317.5
        rot90: false
        flip_x: false
        flip_y: false

Properties
----------

**Hamamatsu-specific properties:**

``cooler_mode``: Cooler mode (only in water cooling): 'off', 'on' or 'max'.

``fan_status``: Current camera fan status: 'off', 'on'.

See the base :doc:`camera` class for additional properties.

Commands
--------

See the base :doc:`camera` class documentation.

Datastreams
-----------

See the base :doc:`camera` class documentation.

