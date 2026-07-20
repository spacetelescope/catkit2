Camera (Base class)
===================

This is the camera base class. It abstracts away image acquisition, ROI management, and exposure/gain control
for different camera hardware. It is meant to be subclassed by the specific camera implementation, both for
hardware and simulated devices (see :doc:`camera_sim` for the latter).

**Frame Orientation**

The base camera class supports frame transformations via rotation and flipping. These transformations are applied
after image capture and before the image is submitted to the datastream. The transformations are applied in the
following order:

1. Rotation (rotation by 90 degrees, ``np.rot90``)
2. Flip X (vertical flip, ``np.flipud``)
3. Flip Y (horizontal flip, ``np.fliplr``)

**Region of Interest (ROI)**

All cameras support configurable regions of interest (ROI) defined by:

- ``width``: The width of the ROI in pixels
- ``height``: The height of the ROI in pixels
- ``offset_x``: The x-offset of the top-left corner of the ROI on the sensor
- ``offset_y``: The y-offset of the top-left corner of the ROI on the sensor

If width and height are not specified, they default to the full sensor size.
If offset_x and offset_y are not specified, they default to (0, 0).

All ROI coordinates are expressed in the **camera coordinate system**. With issue #449, we wand to change this
to make all ROI coordinates in the user coordinate system (i.e., the coordinate system after
frame transformations). The camera base class abstraction would handle the conversion to camera coordinates internally.

Configuration
-------------

.. code-block:: YAML

    camera1:
      service_type: <camera_type>
      simulated_service_type: camera_sim
      requires_safety: false

      # ROI configuration (all optional)
      width: <width>                    # Defaults to sensor_width
      height: <height>                  # Defaults to sensor_height
      offset_x: 0                       # Defaults to 0
      offset_y: 0                       # Defaults to 0

      # Exposure and gain configuration
      exposure_time: 1000               # Exposure time in microseconds. Defaults to 1000
      gain: 0                           # Gain setting. Defaults to 0

      # Frame transformation configuration (all optional)
      rot90: false                      # Rotate image by 90 degrees. Defaults to false
      flip_x: false                     # Flip image horizontally (vertical flip). Defaults to false
      flip_y: false                     # Flip image vertically (horizontal flip). Defaults to false

Properties
----------

**ROI Properties:**

``width``: The width of the ROI in the user coordinate system (in pixels). Requires stopped acquisition to change on most cameras.

``height``: The height of the ROI in the user coordinate system (in pixels). Requires stopped acquisition to change on most cameras.

``offset_x``: The x-offset of the ROI in the user coordinate system (in pixels). Requires stopped acquisition to change on most cameras.

``offset_y``: The y-offset of the ROI in the user coordinate system (in pixels). Requires stopped acquisition to change on most cameras.

**Exposure and Gain Properties:**

``exposure_time``: Exposure time in microseconds. Requires stopped acquisition to change on most cameras.

``gain``: Gain setting. Requires stopped acquisition to change on most cameras.

**Sensor Properties (read-only):**

``sensor_width``: The width of the camera sensor in pixels (in the user coordinate system, after potential rot90 transformations).

``sensor_height``: The height of the camera sensor in pixels (in the user coordinate system, after potential rot90 transformations).

Commands
--------

``start_acquisition()``: Starts the acquisition of images from the camera. Images will be streamed to the ``images`` datastream.

``end_acquisition()``: Stops the acquisition of images from the camera.

Datastreams
-----------

``images``: Images acquired by the camera as float32 arrays with shape [height, width].

``temperature``: The temperature (in Celsius) as measured by the camera, updated approximately every second.

``is_acquiring``: Integer flag (0 or 1) indicating whether the camera is currently acquiring images.

