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
            if self._device_actuator_mask.ndim <= 1:
                raise ValueError(f'The provided device actuator mask needs for {self.service_id} to be at least a 2D array.')
            elif self._device_actuator_mask.ndim == 2:
                self._device_actuator_mask = np.expand_dims(self._device_actuator_mask, axis=0)

        return self._device_actuator_mask

    @property
    def dm_shape(self):
        return self.device_actuator_mask[0].shape

    @property
    def num_dms(self):
        return self.device_actuator_mask.shape[0]

    @property
    def num_actuators(self):
        return np.sum(self.device_actuator_mask[0])

    @property
    def actuator_grid(self):
        # Get the last two dimensions in reverse order.
        dims = self.device_actuator_mask.shape[:-3:-1]

        return hcipy.make_uniform_grid(dims, dims)

    def flatten_channels(self, channel_names):
        summed_command = 0

        if isinstance(channel_names, str):
            channel_names = [channel_names]

        # Get commands from channels, zero each channel, and sum commands.
        for channel_name in channel_names:
            summed_command += getattr(self, channel_name).get()
            self.apply_shape(channel_name, np.zeros(self.num_actuators * self.num_dms))

        # Return summed command (note that this is not a DM map).
        return summed_command

    def dm_maps_to_command(self, dm_map):
        """Convert a 2D Dm map or cube of 2D DM maps to a DM command.

        Parameters
        ----------
        dm_map : array
            A 3D array with its first dimension giving the number of devices controlled with this service. Second and
            third dimension are 2D DM maps. Can also just be a 2D DM map.

        Returns
        -------
        array
            A 1D array containing the DM command.
        """
        if dm_map.ndim == 2:
            dm_map = np.expand_dims(dm_map, axis=0)
        command = dm_map[self.device_actuator_mask]

        return command

    def command_to_dm_maps(self, command):
        """Convert a 1D DM command into a 3D cube of 2D DM maps.

        Parameters
        ----------
        command : array
            A 1D array containing the DM command.

        Returns
        -------
        array
            A 3D array with its first dimension giving the number of devices controlled with this service. Second and
            third dimension are 2D DM maps.
        """
        dm_maps = np.zeros_like(self.device_actuator_mask, dtype='float')

        dm_maps[self.device_actuator_mask] = command

        return dm_maps

    def apply_shape(self, channel, command):
        """
        Apply a shape to a DM channel.

        Parameters
        ----------
        channel : str
            The channel to apply the shape to.
        command : array
            The command to apply to the channel. Can be either a 1D array (DM command) with all actuators of all DMs
            controlled by this driver in sequence. Or a 2D array (cube of 2D arrays) representing all 2D DM maps of all
            DMs controlled by this driver.
        """
        command = np.array(command, copy=False)

        if command.ndim == 1:  # Input is already a (N) array, in which case it is already a DM command.
            pass
        elif 1 < command.ndim <= 3:  # Input is a 2D map or a 3D cube of maps.
            command = self.dm_maps_to_command(command)
        else:
            raise ValueError(f'Invalid shape for command: {command.shape}')

        getattr(self, channel).submit_data(command)
