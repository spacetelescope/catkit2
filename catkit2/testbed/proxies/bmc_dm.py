from ..service_proxy import ServiceProxy

import numpy as np
from astropy.io import fits

@ServiceProxy.register_service_interface('bmc_dm')
class BmcDmProxy(ServiceProxy):
    @property
    def dm_mask(self):
        if not hasattr(self, '_dm_mask'):
            fname = self.configuration['dm_mask_fname']

            self._dm_mask = fits.getdata(fname).astype('bool')

        return self._dm_mask

    def dm_shapes_to_command(self, dm1_shape, dm2_shape=None):
        command = np.zeros(2048)

        if dm2_shape is None:
            command[:952] = dm1_shape[:952]
            command[1024:1024 + 952] = dm1_shape[952:]
        else:
            command[:952] = dm1_shape[self.dm_mask]
            command[1024:1024 + 952] = dm2_shape[self.dm_mask]

        return command

    def command_to_dm_shapes(self, command):
        dm1_shape = np.zeros((34, 34))
        dm2_shape = np.zeros((34, 34))

        dm1_shape[self.dm_mask] = command[:952]
        dm2_shape[self.dm_mask] = command[1024:1024 + 952]

        return dm1_shape, dm2_shape

    def apply_shape(self, channel, dm1_shape, dm2_shape=None):
        command = self.dm_shapes_to_command(dm1_shape, dm2_shape)

        getattr(self, channel).submit_data(command)


def make_poke(actuators, amplitude = quantity(700, units.nanometer), bias = False, flat_map = True, return_shortname = False, dm_num = 1):
    """
    Creates a 1D array DM command that can poke actuators at a given amplitude.
    :param actuators: List of actuators, or a single actuator.
    :param amplitude: Nanometers of amplitude
    :param bias: Boolean flag for whether to apply a bias.
    :param flat_map: Boolean flag for whether to apply a flat_map.
    :param return_shortname: Boolean flag that will return a string that describes the object as the second parameter.
    :param dm_num: 1 or 2, for DM1 or DM2.
    :return: 1d list size 2x952
    """

    short_name = "poke"
    total_actuators = 2*952
    poke_array = np.zeros(total_actuators)

    # Convert peak the valley from a quantity to nanometers, and get the magnitude.
    amplitude = amplitude.to(units.meter).m

    # Bias.
    if flat_map:
        short_name += "_flat_map"
    if bias:
        short_name += "_bias"

    if isinstance(actuators, list):
        for actuator in actuators:
            poke_array[actuator] = amplitude
            short_name += "_" + str(actuator)
    else:
        short_name += "_" + str(actuators)
        poke_array[actuators] = amplitude


    if return_shortname:
        return poke_array, short_name
    else:
        return poke_array



