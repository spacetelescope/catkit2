Allied Vision Camera
====================

.. note::
    This service inherits from the base :doc:`camera` base class.

This service controls an Allied Vision camera. It is a wrapper around the Vimba SDK, which requires its installation.
The service uses the Python API for Vimba X SDK, called ``VmbPy``.
In order to be able to run this service, the camera needs to be set up with the right Allied Vision USB driver.
If the device is also controlled through other interfaces, for example NI MAX, you need to switch back to the right
driver through that interface.

Vimba X SDK: `https://www.alliedvision.com/en/products/software/ <https://www.alliedvision.com/en/products/software/>`_
``VmbPy`` Python API: `https://github.com/alliedvision/VmbPy <https://github.com/alliedvision/VmbPy>`_

.. note::
   The current catkit2 environment file installs the legacy VimbaPython package instead of the required VmbPy package.
   This is because the VmbPy package is not available on any conda channel or PyPI. To install the VmbPy package, you
   need to install it from source as described under the link above.

The service has been successfully tested with the following camera models:

- Alvium 1800 U-158m
- Alvium 1800 U-500m

Configuration
-------------

In addition to the base camera configuration, the following Allied Vision-specific options are available:

.. code-block:: YAML

    camera1:
        service_type: allied_vision_camera
        simulated_service_type: camera_sim
        requires_safety: false

        camera_id: "DEV_1AB22C011222"
        device_name: AV Alvium 1800 U-158m   # Unused in code

        # Base camera configuration
        width: 32
        height: 32
        offset_x: 0
        offset_y: 0
        exposure_time: 200
        gain: 0
        rot90: false
        flip_x: false
        flip_y: false

Properties
----------

**Allied Vision-specific properties:**

``brightness``: Brightness of the camera.

``device_name``: The name of the camera - just for user reference, not used in code.

See the base :doc:`camera` class for additional properties.

Commands
--------

See the base :doc:`camera` class documentation.

Datastreams
-----------

See the base :doc:`camera` class documentation.

