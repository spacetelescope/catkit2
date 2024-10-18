Camera Simulator
================
This service operates a simulated camera. This service is meant to mimic, but does not actually
control, a hardware camera.

This service can be used to simulate any hardware camera service since they are all written consistently.

Configuration
-------------
.. code-block:: YAML

    camera1:
      service_type: my_camera
      simulated_service_type: camera_sim
      interface: camera
      requires_safety: false

      # Keys used only by hardware service.
      device_name: ZWO ASI178MM
      device_id: 4
      well_depth_percentage_target: 0.65

      # Keys used by simulated and hardware service.
      exposure_time: 1000
      width: 1680
      height: 1680
      offset_x: 336
      offset_y: 204
      gain: 0

Properties
----------
``exposure_time``: Simulated exposure time (in microseconds) of the camera.

``gain``: Simulated gain of the camera.

``width``: The width of the camera frames.

``height``: The height of the camera frames.

``offset_x``: The x offset of the camera frames on the sensor.

``offset_y``: The y offset of the camera frames on the sensor.

``sensor_width``: The width of the simulated sensor.

``sensor_height``: The height of the simulated sensor.

Commands
--------
``start_acquisition()``: This starts the acquisition of images from the camera.

``end_acquisition()``: This ends the acquisition of images from the camera.

Datastreams
-----------
``temperature``: The simulated temperature (in Celsius) as measured by the camera.

``images``: The images acquired by the camera.

``is_acquiring``: Whether the camera is currently acquiring images.
