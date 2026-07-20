ZWO Camera
==========

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
        offset_x: 1038
        offset_y: 1282
        width: 192
        height: 192
        exposure_time: 1000
        gain: 100

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

