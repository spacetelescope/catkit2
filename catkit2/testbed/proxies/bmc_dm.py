from ..service_proxy import ServiceProxy

import numpy as np
from astropy.io import fits
import hcipy


class BmcDmProxy(ServiceProxy):
    @property
    def dm_mask(self):
        if not hasattr(self, '_dm_mask'):
            fname = self.config['dm_mask_fname']

            self._dm_mask = fits.getdata(fname).astype('bool')

        return self._dm_mask

    @property
    def num_actuators(self):
        return self.config['num_actuators']

    @property
    def actuator_grid(self):
        dims = self.dm_mask.shape[::-1]

        return hcipy.make_uniform_grid(dims, dims)

    def dm_shapes_to_command(self, dm1_shape, dm2_shape=None):
        command = np.zeros(2048)

        if dm2_shape is None:
            command[:952] = dm1_shape[:952]
            command[1024:1024 + 952] = dm1_shape[952:]
        else:
            command[:952] = dm1_shape[self.dm_mask]
            command[1024:1024 + 952] = dm2_shape[self.dm_mask]

        return command

    def flatten_channels(self, channel_names):
        summed_command = 0

        if isinstance(channel_names, str):
            channel_names = [channel_names]

        # Get commands from channels, zero each channel, and sum commands
        for channel_name in channel_names:
            summed_command += getattr(self, channel_name).get_latest_frame().data
            self.apply_shape(channel_name, np.zeros(2 * self.num_actuators))

        # Return summed command (note that this is not a DM shape)
        return summed_command

    def command_to_dm_shapes(self, command):
        dm1_shape = np.zeros((34, 34))
        dm2_shape = np.zeros((34, 34))

        dm1_shape[self.dm_mask] = command[:952]
        dm2_shape[self.dm_mask] = command[1024:1024 + 952]

        return dm1_shape, dm2_shape

    def apply_shape(self, channel, dm1_shape, dm2_shape=None):
        command = self.dm_shapes_to_command(dm1_shape, dm2_shape)

        getattr(self, channel).submit_data(command)
