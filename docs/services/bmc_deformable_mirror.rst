Deformable Mirror (Base class)
==============================

This is the deformable mirror base class. It abstracts away the virtual channels, device actuator map and all data
streams. It is meant to be subclassed by the specific DM implementation, both for hardware and software devices.

This service controls any number of DMs as long as they are all controlled by the same driver, and they all use the same
device actuator mask.

This service and all its subclasses allow for exactly two types of commands:
1. "DM command": A 1D device actuator command, which is a 1D array of all individual DM actuator commands concatenated together.
2. "DM map": A 3D cube of DM actuator maps, where the first dimension is the DM index. This is allowed to be a 2D array if there
   is only one DM.

DM commands get extensively used in various experiments and they are easier to create, while DM maps are used and
required for plotting purposes. This division makes it easier to distinguish between them since one is a 1D array and
the other one is a 2/3D array. Any conversion to a device-specific hardware command should be done in the subclass, as
it would only be used for communicating with the hardware devices.

The device actuator mask file needs to be 2D FITS file with the actuator map. The actual device actuators are identified
by the non-zero pixels in the mask. The mask is used to determine the number of actuators and their positions on the
device.

The data streams hold exclusively 1D DM commands, where all device actuators from all DMs are concatenated in sequence.
This means their length is ``self.num_actuators * self.num_dms``, both of which are determined by the device
actuator mask.

Configuration
-------------

.. code-block:: YAML

    deformable_mirror:
      service_type: bmc_deformable_mirror
      simulated_service_type: bmc_deformable_mirror_sim
      interface: deformable_mirror
      requires_safety: false

      device_actuator_mask_fname: !path ../data/dms/DM_2Dmask.fits
      channels:
        - correction_howfs
        - correction_lowfs
        - probe
        - poke
        - aberration
        - atmosphere
        - astrogrid
        - resume

Properties
----------
``channels``: List of command channel names (dict).

Commands
--------
None.

Datastreams
-----------
``total_voltage``: Map of the total voltage applied to each actuator of the DM.

``total_surface``: Map of the total amplitude of each DM actuator (meters).

``channels[channel_name]``: The command per virtual channel, identified by channel name.