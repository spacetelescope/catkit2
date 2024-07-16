FLIR Camera
===========
This service operates an FLIR camera. The following are the different types of FLIR cameras that have been tested and used with catkit2 so far:

- `Teledyne FLIR BFS-U3-63S4M-C <https://wilcoimaging.com/products/teledyne-flir-bfs-u3-63s4m-c?_pos=1&_sid=ff2b850d4&_ss=r>`_

For further documentation, see:

- `image format control <http://softwareservices.flir.com/BFS-U3-200S6/latest/Model/public/ImageFormatControl.html>`_

Note that using FLIR cameras requires a manual installation of drivers from `flir.com. <https://www.flir.com/support-center/iis/machine-vision/knowledge-base/technical-documentation-blackfly-s-usb3/>`_

Configuration
-------------
.. code-block:: YAML

    camera1:
        service_type: flir_camera
        simulated_service_type: camera_sim
        requires_safety: false

        serial_number: 000000
        width: 312
        height: 312
        offset_x: 100
        offset_y: 134
        adc_bit_depth: 12bit
        pixel_format: mono12p
        well_depth_percentage_target: 0.65
        exposure_time: 1000
        gain: 0
        env:
            KMP_DUPLICATE_LIB_OK: TRUE

Properties
----------
``exposure_time``: Exposure time (in microseconds) of the camera.

``gain``: Gain of the camera.

``width``: The width of the camera frames.

``height``: The height of the camera frames.

``offset_x``: The x offset of the camera frames on the sensor.

``offset_y``: The y offset of the camera frames on the sensor.

``sensor_width``: The width of the sensor.

``sensor_height``: The height of the sensor.

``pixel_format``: Format of the pixel provided by the camera.

``adc_bit_depth``: Fixed bit output of the camera ADC.

``acquisition_frame_rate``: Frame rate of the acquisition (if enabled, see below).

``acquisition_frame_rate_enable``: Whether to allow manual control of the acquisition frame rate.

``device_name``: The name of the camera.

Commands
--------
``start_acquisition()``: This starts the acquisition of images from the camera.

``end_acquisition()``: This ends the acquisition of images from the camera.


Datastreams
-----------
``temperature``: The temperature (in Celsius) as measured by the camera.

``images``: The images acquired by the camera.

``is_acquiring``: Whether the camera is currently acquiring images.

