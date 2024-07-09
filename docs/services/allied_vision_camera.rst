Allied Vision Camera
====================

This service controls an Allied Vision camera. It is a wrapper around the Vimba SDK, which requires its installation.
The service uses the Python API for Vimba X SDK, called ``VmbPy``.
In order to be able to run this service, the camera needs to be set up with the right Allied Vision USB driver.
If the device is also controlled through other interfaces, for example NI MAX, you need to switch back to the right
driver through that interface.

Vimba X SDK: `https://www.alliedvision.com/en/products/software/ <https://www.alliedvision.com/en/products/software/>`_
``VmbPy`` Python API: `https://github.com/alliedvision/VmbPy <https://github.com/alliedvision/VmbPy>`_

The service has been successfully tested with the following camera models:

- Alvium 1800 U-158m
- Alvium 1800 U-500m

Configuration
-------------

.. code-block:: YAML

    camera1:
      service_type: allied_vision_camera
      simulated_service_type: camera_sim
      requires_safety: false

      camera_id: "DEV_1AB22C011222"
      device_name: AV Alvium 1800 U-158m

      offset_x: 0
      offset_y: 0
      width: 32
      height: 32
      sensor_width: 1456
      sensor_height: 1088

      exposure_time: 200
      gain: 0

Properties
----------
``exposure_time``: Exposure time of the camera in microseconds.

``gain``: Gain of the camera.

``brightness``: Brightness of the camera.

``width``: The width of the camera frames.

``height``: The height of the camera frames.

``offset_x``: The x offset of the camera frames on the sensor.

``offset_y``: The y offset of the camera frames on the sensor.

``sensor_width``: The width of the sensor.

``sensor_height``: The height of the sensor.

Commands
--------
``start_acquisition()``: This starts the acquisition of images from the camera.

``end_acquisition()``: This ends the acquisition of images from the camera.

Datastreams
-----------
``temperature``: The temperature (in Celsius) as measured by the camera.

``images``: The images acquired by the camera.

``is_acquiring``: Whether the camera is currently acquiring images.