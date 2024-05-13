FLIR Camera
===========

This service connects to a FLIR Backfly camera. Manufacturer informations can be found here: https://www.flir.com/products/blackfly-s-usb3/?vertical=machine%20vision&segment=iis

This service requires the installation of the FLIR drivers than come in the Spinnaker SDK, that can be found here: https://www.flir.com/products/spinnaker-sdk/?vertical=machine+vision&segment=iis .
It also requires the Spinnaker SDK https://pypi.org/project/spinnaker-python/

This service has been successfully tested with the following device on Windows 10, with Python 3.7:
    -

Configuration
-------------

.. code-block:: YAML

    zernike_camera:
      service_type: flir_camera
      simulated_service_type: camera_sim

      requires_safety: false
      serial_number: xxxxxxxx
      width: xxx
      height: xxx
      offset_x: xxx
      offset_y: xxx
      adc_bit_depth: 12bit
      pixel_format: mono12p
      well_depth_percentage_target: 0.65
      exposure_time: 1000
      gain: 0
      env:
        KMP_DUPLICATE_LIB_OK: TRUE

Properties
----------
``device_nme``
``exposure_time``: Exposure time of the camera.

``gain``: Gain of the camera.

``brightness``: Brightness of the camera.

``width``: The width of the ROI.

``height``: The height of the ROI.

``offset_x``: The x offset of the camera.

``offset_y``: The y offset of the camera.

``sensor_width``: The width of the sensor. (Read only)

``sensor_height``: The height of the sensor. (Read only)

``pixel_format``: The pixel data format.

``adc_bit_depth`` The Analog-to-Digital Converter (ADC) bit depth.

        make_property_helper('acquisition_frame_rate')
        make_property_helper('acquisition_frame_rate_enable')

        make_property_helper('device_name', read_only=True)

Commands
--------

Datastreams
-----------
