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


def make_poke(actuators, amplitude = quantity(700, units.nanometer), dm_num = 1):
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
    total_actuators = 2*952
    poke_array = np.zeros(total_actuators)

    # Convert peak the valley from a quantity to nanometers, and get the magnitude.
    amplitude = amplitude.to(units.meter).m

    if isinstance(actuators, list):
        for actuator in actuators:
            poke_array[actuator] = amplitude

    else:
        poke_array[actuators] = amplitude

    return poke_array


def make_poke_f(amplitude = quantity(700, units.nanometer), bias = False, flat_map = True, return_shortname = False, dm_num = 1)

    actuators = [529,599,669,736,799,857,424,354,284,217,154,96,526,559,592,525,658,690,721,751,780,627,692,725,753,784,814,
                810,838,864,888,427,394,361,328,295,263,232,202,173,326,261,228,200,169,139,143,115,89,65]

    total_actuators = 2*952
    poke_array = np.zeros(total_actuators)

    for actuator in actuators:
        poke_array[actuator] = amplitude

    return poke_array

