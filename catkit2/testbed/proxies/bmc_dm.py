from ..service_proxy import ServiceProxy

import numpy as np
from astropy.io import fits
import hcipy

@ServiceProxy.register_service_interface('bmc_dm')
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

    def save_and_zero_channel(self, channel):
        full_command = getattr(self, channel).get_latest_frame().data.copy()
        self.apply_shape(channel, np.zeros(2 * self.num_actuators))

        return full_command

    def move_dm_command(self, from_channel_names):
        move_command = np.zeros(2048)

        # Get commands from channels, zero each channel, and sum commands
        for channel_name in from_channel_names:
            channel_command = self.save_and_zero_channel(channel_name)
            move_command += channel_command

        # Return summed command (note that this is not a DM shape)
        return move_command

    def command_to_dm_shapes(self, command):
        dm1_shape = np.zeros((34, 34))
        dm2_shape = np.zeros((34, 34))

        dm1_shape[self.dm_mask] = command[:952]
        dm2_shape[self.dm_mask] = command[1024:1024 + 952]

        return dm1_shape, dm2_shape

    def apply_shape(self, channel, dm1_shape, dm2_shape=None):
        command = self.dm_shapes_to_command(dm1_shape, dm2_shape)

        getattr(self, channel).submit_data(command)
