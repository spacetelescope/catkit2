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
        dims = self.device_actuator_mask.shape[:-2:-1]

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
        """Convert a cube of 2D DM maps to a DM command.

        Parameters
        ----------
        dm_map : array
            A 3D array with its first dimension giving the number of devices controlled with this service. Second and
            third dimension are 2D DM maps.

        Returns
        -------
        array
            A 1D array containing the DM command.
        """
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
        dm_maps = np.empty_like(self.device_actuator_mask, dtype='float')

        dm_maps[self.device_actuator_mask] = command  # TODO: Is this going to work?

        return dm_maps

    def apply_shape(self, channel, command):
        command = np.array(command, copy=False)

        # TODO: with how many potential cases do we want to deal here?
        # Could be a (N) array, in which case it is already a DM command.
        # Could be a (1, N) array, in which case it is already a DM command, but it needs to be squeezed.
        # Could be a (X, N) array, in which case it is a DM command for multiple DMs, but it needs to be converted to a DM command (just concatenated).
        # Could be a (M, M) array, in which case it is a DM map, but it needs to be converted to a DM command.
        # Could be a (1, M, M) array, in which case it is a DM map, but it needs to be converted to a DM command (and squeezed).
        # Could be a (X, M, M) array, in which case it is DM maps for multiple DMs, but it needs to be converted to a DM command (reshaped and concatenated).

        if command.ndim == 1:    # TODO: 1/6 TESTED AND WORKS
            pass
        elif command.ndim == 2 and command.shape[0] == 1:
            command.squeeze()
        elif command.ndim == 2 and command.shape[0] == self.num_dms:
            command = np.concatenate(command)
        elif command.shape == self.dm_shape:    # TODO: 4/6 TESTED AND WORKS
            command = self.dm_maps_to_command(np.expand_dims(command, axis=0))
        elif command.ndim > 2 and command.shape[0] == 1:    # TODO: 5/6 TESTED AND WORKS
            command = self.dm_maps_to_command(command)
        elif command.ndim > 2 and command.shape[0] == self.num_dms:
            map_to_command = np.zeros_like(command)
            for i, slice in enumerate(command):
                map_to_command[i] = self.dm_maps_to_command(np.expand_dims(slice, axis=0))
            command = np.concatenate(map_to_command)

        getattr(self, channel).submit_data(command)
