Hamamatsu Camera
====================

This service controls a Hamamatsu camera. It is a wrapper around the DCAM SDK, which is distributed on the manufacturer
website together with their Python API ``dcam``: `https://www.hamamatsu.com/eu/en/product/cameras/software/driver-software.html <https://www.hamamatsu.com/eu/en/product/cameras/software/driver-software.html>`_

The service requires the definition of an environment variable ``CATKIT_DCAM_SDK_PATH`` that points to the
``python`` directory within the DCAM SDK installation.

The service has been successfully tested with the following camera models:
- Hamamatsu ORCA-Quest C15550-20UP

Configuration
-------------

.. code-block:: YAML

    camera1:
      service_type: hamamatsu_camera
      simulated_service_type: camera_sim
      requires_safety: false

      camera_id: 0
      camera_mode: 'ultraquiet'
      pixel_format: Mono16
      binning: 1

      offset_x: 0
      offset_y: 0
      width: 400
      height: 400
      sensor_width: 4096
      sensor_height: 2304
      exposure_time: 8294.4
      gain: 0

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

Commands
--------
``start_acquisition()``: This starts the acquisition of images from the camera.

``end_acquisition()``: This ends the acquisition of images from the camera.

Datastreams
-----------
``temperature``: The temperature as measured by this sensor in Celsius.

``images``: The images acquired by the camera.

``is_acquiring``: Whether the camera is currently acquiring images.