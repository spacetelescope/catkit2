Ocean Optics Spectrometer
=========================

This service controls an Ocean Optics Spectrometer. It is a wrapper around the python-seabreeze package.
The python-seabreeze package needs to be installed first, and the page also explain how to install the
spectrometer drivers needed for windows.

python-seabreeze package: `https://python-seabreeze.readthedocs.io/ <https://python-seabreeze.readthedocs.io/>`_

The service has been successfully tested with the following ocean optics spectrometer:

- USB4000 Spectrometer

Configuration
-------------

.. code-block:: YAML

  spectrometer:
    service_type: oceanoptics_spectrometer
    simulated_service_type: oceanoptics_spectrometer_sim
    interface: oceanoptics_spectrometer
    requires_safety: false

    serial_number: USB4C01580 # Serial number of the spectrometer.
    exposure_time: 1000       # Exposure time of the spectrometer in microseconds.
    interval: 0.01            # Interval between measurements, in seconds.

Properties
----------
``exposure_time``: Exposure time of the spectrometer in microseconds.

``wavelengths``:  Wavelengths in (nm) corresponding to each pixel of the spectrometer

Commands
--------

Datastreams
-----------
``spectra``: Spectra acquired by the camera.

``is_saturating``: If the intensity as reached the maximum value of the spectrometer.