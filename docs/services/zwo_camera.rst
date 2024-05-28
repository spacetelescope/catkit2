ZWO Camera
==========

This service operates a ZWO camera. The following are the different types of ZWO cameras that have been tested and used with catkit2 so far:

- `ZWO ASI533MM <https://www.zwoastro.com/product/asi533mm-mc/>`_
- `ZWO ASI290MM <https://agenaastro.com/zwo-asi290mm-cmos-monochrome-astronomy-imaging-camera.html>`_
- `ZWO ASI178MM <https://agenaastro.com/zwo-asi178mm-cmos-monochrome-astronomy-imaging-camera.html>`_
- `ZWO ASI1600MM <https://agenaastro.com/zwo-asi1600mm-p-cmos-monochrome-astronomy-imaging-camera-pro.html>`_

For camera specs, see the website links above.
Note that using ZWO cameras requires a manual installation of drivers from `zwoastro.com <https://astronomy-imaging-camera.com/software-drivers>`_ 

Configuration
-------------

.. code-block:: YAML

    camera1:
        service_type: zwo_camera
        simulated_service_type: camera_sim
        requires_safety: false

        device_name: ZWO ASI533MM
        offset_x: 1038
        offset_y: 1282
        width: 192
        height: 192
        exposure_time: 1000
        gain: 100

Properties
----------
``exposure_time``: Exposure time of the camera.

``gain``: Gain of the camera.

``brightness``: Brightness of the camera.

``width``: The width of the camera frames.

``height``: The height of the camera frames.

``offset_x``: The x offset of the camera frames on the sensor.

``offset_y``: The y offset of the camera frames on the sensor.

``sensor_width``: The width of the sensor.

``sensor_height``: The height of the sensor.

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
