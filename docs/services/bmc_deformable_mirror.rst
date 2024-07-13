BMC Deformable Mirror (Inherits from DeformableMirror)
======================================================

This is a base class for Boston Micromachines DMs, which inherits from the general DM base class. This BMC base class
abstracts away the discretization of the voltage and total surface, as well as the handling of the flat maps and gain
maps.

The provided flat maps and gain maps need to be 2D FITS files. The file given in the configuration can also be a cube of
2D flat maps or gain maps, respectively. There are two service attributes associated with the flat map and gain map:
- ``self.flat_map``/``self.gain_map``: The flat map (gain map) data in the form of a 3D cube. The first dimension always
  corresponds to the number of DMs controlled by the service.
- ``self.flat_map_command``/``self.gain_map_command``: The flat maps (gain maps) in the form of a 1D Dm command. These
  are capable of operating on other DM commands.

The child hardware service is ``BmcDeformableMirrorHardware``, and the child simulated service is
``BmcDeformableMirrorSim``. While the simulated service talks directly to a simulator, the hardware service talks to the
actual hardware. The latter performs a conversion to the actual hardware device command by reading an optional command
starting index ``device_command_index`` from the service configuration. This parameter has three value options:
- *Undefined*: Zero will be assumed as the hardware command index.
- *Integer*: If only one device is controlled by the service, using a non-zero starting index for its hardware command.
- *List of integers*: If multiple devices with the same number of actuators are controlled by the service.

Configuration
-------------

.. code-block:: YAML

    boston_dm:
      service_type: bmc_deformable_mirror_hardware
      simulated_service_type: bmc_deformable_mirror_sim
      interface: deformable_mirror
      requires_safety: false

      serial_number: 00XX000#000
      dac_bit_depth:
      max_volts: 200

      device_actuator_mask_fname: !path ../data/boston_dms/DM_2Dmask.fits
      flat_map_fname: !path ../data/boston_dms/flat_map_2D.fits
      gain_map_fname: !path ../data/boston_dms/gain_map_2D.fits

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
See ``DeformableMirror``.

Commands
--------
None.

Datastreams
-----------
See ``DeformableMirror``.