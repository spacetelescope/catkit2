FLIR Camera
===========
This service operates an FLIR camera. The following are the different types of FLIR cameras that have been tested and used with catkit2 so far:

- `Teledyne FLIR BFS-U3-63S4M-C <https://wilcoimaging.com/products/teledyne-flir-bfs-u3-63s4m-c?_pos=1&_sid=ff2b850d4&_ss=r>`_

For further documentation, see:

- `image format control <http://softwareservices.flir.com/BFS-U3-200S6/latest/Model/public/ImageFormatControl.html>`_

Note that using FLIR cameras requires a manual installation of drivers from `flir.com. <https://www.flir.com/support-center/iis/machine-vision/knowledge-base/technical-documentation-blackfly-s-usb3/>`_

Configuration
-------------

In addition to the base camera configuration, the following FLIR-specific options are available:

.. code-block:: YAML

    camera1:
        service_type: flir_camera
        simulated_service_type: camera_sim
        requires_safety: false

        serial_number: 000000
        adc_bit_depth: 12bit
        pixel_format: mono12p
        well_depth_percentage_target: 0.65
        env:
            KMP_DUPLICATE_LIB_OK: TRUE

        # Base camera configuration
        width: 312
        height: 312
        offset_x: 100
        offset_y: 134
        exposure_time: 1000
        gain: 0
        rot90: false
        flip_x: false
        flip_y: false

Properties
----------

**FLIR-specific properties:**

``pixel_format``: Format of the pixel provided by the camera.

``adc_bit_depth``: Fixed bit output of the camera ADC.

``acquisition_frame_rate``: Frame rate of the acquisition (if enabled, see below).

``acquisition_frame_rate_enable``: Whether to allow manual control of the acquisition frame rate.

``device_name``: The name of the camera.

See the base :doc:`camera` class for additional properties.

Commands
--------

See the base :doc:`camera` class documentation.

Datastreams
-----------

See the base :doc:`camera` class documentation.

