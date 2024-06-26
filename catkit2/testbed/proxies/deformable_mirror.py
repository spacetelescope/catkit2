from ..service_proxy import ServiceProxy

import numpy as np
from astropy.io import fits
import hcipy

@ServiceProxy.register_service_interface('deformable_mirror')
class DeformableMirrorProxy(ServiceProxy):
    @property
    def device_actuator_mask(self):
        if not hasattr(self, '_device_actuator_mask'):
            fname = self.config['device_actuator_mask_fname']

            self._device_actuator_mask = fits.getdata(fname).astype('bool')

        return self._device_actuator_mask

    @property
    def dm_shape(self):
        return self.device_actuator_mask.shape

    @property
    def num_actuators(self):
        return np.sum(self.device_actuator_mask)

    @property
    def actuator_grid(self):
        # Get the last two dimensions in reverse order.
        dims = self.device_actuator_mask.shape[:-2:-1]

        return hcipy.make_uniform_grid(dims, dims)

    def flatten_channels(self, channel_names):
        summed_command = 0

        if isinstance(channel_names, str):
            channel_names = [channel_names]

        # Get commands from channels, zero each channel, and sum commands.
        for channel_name in channel_names:
            summed_command += getattr(self, channel_name).get()
            self.apply_shape(channel_name, np.zeros(self.num_actuators))

        # Return summed command (note that this is not a DM map).
        return summed_command

    def dm_maps_to_command(self, dm_map):
        command = dm_map[self.device_actuator_mask]

        return command

    def command_to_dm_maps(self, command):
        dm_maps = np.empty_like(self.device_actuator_mask, dtype='float')

        dm_maps[self.device_actuator_mask] = command

        return dm_maps

    def apply_shape(self, channel, command):
        command = np.array(command, copy=False)

        # Convert DM maps to command if it's not already a command.
        if command.ndim != 1:
            command = self.dm_maps_to_command(command)

        getattr(self, channel).submit_data(command)
