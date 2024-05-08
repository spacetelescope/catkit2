ZWO Camera
==========

This service operates a ZWO camera. There are currently four different types of ZWO cameras being used on the testbed:
- ZWO ASI533MM (Science camera, https://www.zwoastro.com/product/asi533mm-mc/)
- ZWO ASI290MM (TA camera, https://agenaastro.com/zwo-asi290mm-cmos-monochrome-astronomy-imaging-camera.html)
- ZWO ASI178MM (MOWFS Camera and Pupil Camera, https://agenaastro.com/zwo-asi178mm-cmos-monochrome-astronomy-imaging-camera.html)
- ZWO ASI1600MM (Phase Retrieval Camera, https://agenaastro.com/zwo-asi1600mm-p-cmos-monochrome-astronomy-imaging-camera-pro.html)

For camera specs, see the website links above.

Configuration
-------------

.. code-block:: YAML

    science_camera:
        service_type: zwo_camera
        simulated_service_type: camera_sim
        interface: hicat_camera
        requires_safety: false

        device_name: ZWO ASI533MM
        offset_x: 1038
        offset_y: 1282
        width: 192
        height: 192
        well_depth_percentage_target: 0.65
        exposure_time: 1000
        gain: 100
        exposure_time_step_size: 33
        exposure_time_offset_correction: -79.2
        exposure_time_base_step: 50

    ta_camera:
        service_type: zwo_camera
        simulated_service_type: camera_sim
        interface: hicat_camera
        requires_safety: false

        device_name: ZWO ASI290MM
        device_id: 1
        offset_x: 496
        offset_y: 462
        width: 464
        height: 464
        well_depth_percentage_target: 0.65
        exposure_time: 100000
        gain: 0

    mowfs_camera:
        service_type: zwo_camera
        simulated_service_type: camera_sim
        interface: hicat_camera
        requires_safety: false

        device_name: ZWO ASI178MM
        device_id: 3
        offset_x: 1208
        offset_y: 1256
        width: 824
        height: 824
        well_depth_percentage_target: 0.65
        exposure_time: 1000
        gain: 0

    pupil_camera:
        service_type: zwo_camera
        simulated_service_type: camera_sim
        interface: hicat_camera
        requires_safety: false

        device_name: ZWO ASI178MM
        device_id: 4
        well_depth_percentage_target: 0.65
        exposure_time: 1000
        width: 1680
        height: 1680
        offset_x: 336
        offset_y: 204
        gain: 0

    phase_retrieval_camera:
        service_type: zwo_camera
        simulated_service_type: camera_sim
        interface: hicat_camera
        requires_safety: false

        device_name: ZWO ASI1600MM
        device_id: # This camera does not have device_id
        offset_x: 1700
        offset_y: 1364
        width: 1024
        height: 1024
        well_depth_percentage_target: 0.65
        exposure_time: 10000
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

``device_name``: The name of the camera.

Commands
--------
``start_acquisition()``: This starts the acquisition of images from the camera.

``end_acquisition()``: This ends the acquisition of images from the camera.

``take_calibrated_exposures(num_exposures, only_use_cache=True)``: This takes a number of calibrated exposures.

``get_exposure_calibration_function(only_use_cache=True)``: This gets a function to calibrate individual exposures.

``take_calibrated_image(num_exposures, upsample_factor=None, alignment_window=None, only_use_cache=True)``: This takes a calibrated 
image which is background subtracted, exposure time corrected, nd flux calibrated and sub-frame aligned using phase cross correlation method.

``take_dark(num_exposures)``: This takes a dark image for the current exposure time by moving the beam dump.

Datastreams
-----------
``temperature``: The temperature as measured by this sensor in Celsius.

``images``: The images acquired by the camera.

``is_acquiring``: Whether the camera is currently acquiring images.
