ZWO Camera
==========

.. note::
    This service inherits from the base :doc:`camera` base class.

This service operates a ZWO camera. The following are the different types of ZWO cameras that have been tested and used with catkit2 so far:

- `ZWO ASI533MM <https://www.zwoastro.com/product/asi533mm-mc/>`_
- `ZWO ASI290MM <https://agenaastro.com/zwo-asi290mm-cmos-monochrome-astronomy-imaging-camera.html>`_
- `ZWO ASI178MM <https://agenaastro.com/zwo-asi178mm-cmos-monochrome-astronomy-imaging-camera.html>`_
- `ZWO ASI1600MM <https://agenaastro.com/zwo-asi1600mm-p-cmos-monochrome-astronomy-imaging-camera-pro.html>`_

For camera specs, see the website links above.

Note that using ZWO cameras requires a manual installation of the ZWO SDK from `zwoastro.com <https://www.zwoastro.com/layouts/download-others/>`_
It also requires the setup of the environment variable ``ZWO_ASI_LIB`` to point to the right file from the SDK depending
on your operating system. For example, on Windows, you would set ``ZWO_ASI_LIB`` to the path of the ``ASICamera2.dll``
file from the SDK; for Linux, you would set it to the path of the ``libASICamera2.so`` file from the SDK.

Configuration
-------------

In addition to the base camera configuration, the following ZWO-specific options are available:

.. code-block:: YAML

    camera1:
        service_type: zwo_camera
        simulated_service_type: camera_sim
        requires_safety: false

        device_name: ZWO ASI533MM

        # Base camera configuration
        width: 192
        height: 192
        offset_x: 1038
        offset_y: 1282
        exposure_time: 1000
        gain: 100
        rot90: false
        flip_x: false
        flip_y: false

Properties
----------

**ZWO-specific properties:**

``brightness``: Brightness of the camera.

``device_name``: The name of the camera.

``max_bandwidth``: The camera USB bandwidth setting. True uses (default) max USB bandwidth setting. False sets minimum USB bandwidth which can be more reliable in some situations.

See the base :doc:`camera` class for additional properties.

Commands
--------

See the base :doc:`camera` class documentation.

Datastreams
-----------

See the base :doc:`camera` class documentation.


Calibrated exposure (zwo_camera_v2)
-----------------------------------

Call ``camera.raw_exposure_time()`` for a live SDK exposure control readback
in microseconds. Call ``camera.raw_exposure_time(command_us=12)`` to write an
integer ASI exposure command and return the live readback. Each command
bypasses the configured exposure mapping. Without an
``exposure_calibration`` mapping, ``exposure_time`` keeps its existing
step, base and offset behavior. A null or false mapping also disables it.

The following synthetic example uses a measured floor, a regular grid and one
command whose stair index differs from the grid. Use an instance-specific map
only after verifying the SDK readback and the commanded setting represent the
same stair throughout the declared range for the camera, SDK and ROI in use.

.. code-block:: yaml

    exposure_time: 0
    exposure_calibration:
        command_range_us: [0, 22]
        first_boundary_us: 8
        step_commands_us: 4
        floor_index: -1
        index_corrections: {"12": -1}
        k0: -2
        duration_scale_us: 3
        sdk_readback_same_stair_verified: true

For integer command or readback ``c``, the nominal index is
``floor((c - first_boundary_us) / step_commands_us)``. Add the optional
command-specific index correction and clamp the result to the measured
``floor_index`` from below. Duration in microseconds is
``duration_scale_us * (index - k0)``. The scale and zero are supplied by the
calibration. A photometric zero alone does not establish an absolute timing scale.

With calibration enabled, ``exposure_time`` selects the nearest reachable
duration. An exact tie selects the shorter duration. The representative is the
first integer command on that stair within both the calibrated and SDK control
limits. A zero request selects the minimum. Other requests, including the
initial configured exposure, must lie between the read-only
``minimum_calibrated_exposure_time`` and ``maximum_calibrated_exposure_time``.

After a write through either interface, the service publishes the exposure
property from the SDK readback. A calibrated write that lands on a different stair raises an
error. A raw write can set an exposure outside the mapping, in which case
the proxy reports ``exposure_time`` as ``None`` until a later in-range write.
Proxy reads return the last published values at startup or a service write.
