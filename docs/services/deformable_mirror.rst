Deformable Mirror (Base class)
==============================

This is the deformable mirror base class. It abstracts away the virtual channels, device actuator map and all data
streams. It is meant to be subclassed by the specific DM implementation, both for hardware and software devices.

This service controls any number of DMs as long as they are all controlled by the same driver, and they all use the same
shape (optionally zero-padded).

This service and all its subclasses allow for exactly two types of commands:
1. "DM command". A 1D array containing all individual DM actuator commands concatenated together.
2. "DM map". A multidimensional stack of DM actuator maps, where the first dimension is the DM index.

DM commands are used extensively in various experiments and are easier to create, while DM maps are used for plotting purposes.
This division makes it easier to distinguish between them since one is a 1D array and
the other one is not. Any conversion to a device-specific hardware command should be done in the subclass, as
it would only be used for communicating with the hardware devices.

The device actuator mask file needs to be a FITS file in DM map format. The actual device actuators are identified
by the non-zero pixels in the mask. The mask is used to determine the number of actuators and their positions on the
device.

The data streams hold exclusively 1D DM commands, where all device actuators from all DMs are concatenated in sequence.

At startup, each channel will have an optional startup map applied.

Configuration
-------------
This service cannot be used as-is since it lacks an implementation of the ``send_surface()`` method. It is meant to be
subclassed by the specific DM implementation, both for hardware and software devices.

Properties
----------
``channels``: List of command channel names (dict).

Commands
--------
None.

Datastreams
-----------
``total_voltage``: Array of the total voltage applied to each actuator of the DM.

``total_surface``: Array of the total amplitude of each DM actuator (nm).

``channels[channel_name]``: The command per virtual channel, identified by channel name, in nm surface.
