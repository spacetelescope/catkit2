ZWO Camera
==========

This service operates a ZWO camera. There are currently four different types of ZWO cameras that have been tested and used with catkit2 so far:
- ZWO ASI533MM (https://www.zwoastro.com/product/asi533mm-mc/)
- ZWO ASI290MM (https://agenaastro.com/zwo-asi290mm-cmos-monochrome-astronomy-imaging-camera.html)
- ZWO ASI178MM (https://agenaastro.com/zwo-asi178mm-cmos-monochrome-astronomy-imaging-camera.html)
- ZWO ASI1600MM (https://agenaastro.com/zwo-asi1600mm-p-cmos-monochrome-astronomy-imaging-camera-pro.html)

For camera specs, see the website links above.

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

``width``: The width of the camera.

``height``: The height of the camera.

``offset_x``: The x offset of the camera.

``offset_y``: The y offset of the camera.

``sensor_width``: The width of the sensor.

``sensor_height``: The height of the sensor.

``device_name``: The name of the camera.

Commands
--------
``start_acquisition()``: This starts the acquisition of images from the camera.

``end_acquisition()``: This ends the acquisition of images from the camera.

Datastreams
-----------
``temperature``: The temperature as measured by this sensor in Celsius.

``images``: The images acquired by the camera.

``is_acquiring``: Whether the camera is currently acquiring images.
