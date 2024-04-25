NI DAQ
======

This service controls a National Instruments DAQ card. It is implemented similarly to a deformable mirror in such that
it has a set of virtual channels that can be controlled independently. The total voltage output by the NI DAQ is the sum
of all the channels.

The service requires installation of the NI-DAQmx driver. The driver can be downloaded from the National Instruments website.
It uses the Python API provided by the ``nidaqmx`` package.

Configuration
-------------

.. code-block:: YAML

    piezo_tip_tilt:
      service_type: ni_daq
      simulated_service_type: ni_daq_sim
      interface: ni_daq
      requires_safety: false

      device_name: Dev1
      daq_input_channels: []
      daq_output_channels: [ao0, ao1]
      volt_limit_min: -2.
      volt_limit_max: 2.

      channels:
      - target_acquisition
      - aberration
      - correction

Properties
----------
None.

Commands
--------
None.

Datastreams
-----------
``total_voltage``: The total voltage output by the NI DAQ. This is the sum of the voltages output by each virtual channel.

``channels[channel_name]``: The command per virtual channel, identified by channel name.
