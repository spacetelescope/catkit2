AccuFiz Interferometer
==========

This service operates a 4D Technologies AccuFiz Interferometer using the 4D InSight software and their Web Services API for communication. It handles image acquisition, processing, and data management.

Configuration
-------------

.. code-block:: YAML

    accufiz_interferometer:
        service_type: accufiz_interferometer
        simulated_service_type: accufiz_interferometer_sim
        interface: camera
        requires_safety: false
        height: 1967
        width: 1970
        sim_data: C:/path/to/example.h5
        mask: C:/path/to/4d.mask
        server_path: C:/path/to/data
        local_path: C:/path/to/data
        ip_address: localhost:8080
        save_h5: true
        save_fits: false
        num_avg: 2
        fliplr: true
        rotate: 0

Properties
-----------
``mask``: Path to the mask file to be used by the interferometer.

``server_path``: Directory path on the server where measurement data will be saved.

``local_path``: Local directory path where measurement data will be saved.

``ip_address``: IP address and port of the 4D InSight Web Services API. Default is 'localhost:8080'.

``calibration_data_package``: Path to the calibration data package (optional).

``timeout``: Timeout in milliseconds for the Web Services API requests. Default is 10000.

``post_save_sleep``: Time in seconds to wait after saving data. Default is 1.

``file_mode``: Whether to operate in file mode. Default is True.

``height``: Height of the image frames captured by the interferometer. Default is 1967.

``width``: Width of the image frames captured by the interferometer. Default is 1970.

``config_id``: Configuration identifier for logging purposes. Default is 'accufiz'.

``save_h5``: Whether to save measurement data in HDF5 format. Default is True.

``save_fits``: Whether to save processed images in FITS format. Default is False.

``num_avg``: Number of frames to average when taking a measurement. Default is 2.

``fliplr``: Whether to flip the image horizontally. Default is True.

``rotate``: Rotation angle in degrees for the image. Default is 0.

Commands
-----------
``start_acquisition()``: Starts the continuous data acquisition process.

``end_acquisition()``: Ends the continuous data acquisition process.

``take_measurement()``: Takes a single measurement and processes the image.

Datastreams
-----------
``images``: The processed images acquired from the interferometer.

``detector_masks``: The detector masks used during measurements.

``is_acquiring``: Indicates whether the service is currently acquiring data (1 for acquiring, 0 for not acquiring).

Notes
The AccuFiz Interferometer requires the 4D InSight software to be in listening mode and WebServices4D to be installed and configured correctly.

The service communicates with the interferometer using HTTP requests to the Web Services API provided by the 4D InSight software and Web Service.

Ensure that the mask file specified in the configuration is accessible to the 4D computer.
