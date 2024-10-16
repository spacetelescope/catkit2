from ..service_proxy import ServiceProxy

import numpy as np
from astropy.io import fits
import hcipy


class DeformableMirrorProxy(ServiceProxy):
    @property
    def device_actuator_mask(self):
        '''A mask describing the physical actuators on all DMs.
        '''
        if not hasattr(self, '_device_actuator_mask'):
            fname = self.config['device_actuator_mask_fname']
            self._device_actuator_mask = fits.getdata(fname).astype('bool')

            if self._device_actuator_mask.ndim <= 1:
                raise ValueError(f'The provided device actuator mask needs for {self.service_id} to be at least a 2D array.')

        return self._device_actuator_mask

    @property
    def command_length(self):
        '''The length of a DM command.
        '''
        return np.sum(self.device_actuator_mask)

    @property
    def dm_shape(self):
        '''The shape of the DM.
        '''
        return self.device_actuator_mask[0].shape

    @property
    def num_dms(self):
        '''The number of DMs.
        '''
        return self.device_actuator_mask.shape[0]

    @property
    def num_actuators(self):
        '''The number of device actuators per DM.
        '''
        return np.sum(self.device_actuator_mask[0])

    @property
    def actuator_grid(self):
        '''The positions of the actuators of the DM(s).
        '''
        # Get the last dimensions in reverse order.
        dims = self.device_actuator_mask.shape[1:][::-1]

        return hcipy.make_uniform_grid(dims, dims)

    def flatten_channels(self, channel_names):
        '''Flatten the designated channels.

        Parameters
        ----------
        channel_names : list of str, or str
            The channel name(s) which to flatten.

        Returns
        -------
        ndarray
            The summed DM command of the flattened channels.
        '''
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
            The DM map for each device.

        Returns
        -------
        array
            A 1D array containing the DM command.
        """
        try:
            dm_map = np.broadcast_to(dm_map, self.device_actuator_mask.shape)
        except ValueError:
            raise ValueError(f'Invalid shape for dm map: {dm_map.shape}. Expected shape: {self.device_actuator_mask.shape}.')

        command = dm_map[self.device_actuator_mask]

        return command

    def command_to_dm_maps(self, command):
        """Convert a DM command into DM maps.

        Parameters
        ----------
        command : ndarray
            A 1D array containing the DM command.

        Returns
        -------
        ndarray
            The DM maps for each device.
        """
        dm_maps = np.zeros_like(self.device_actuator_mask, dtype='float')
        dm_maps[self.device_actuator_mask] = command

        return dm_maps

    def apply_shape(self, channel, dm_shape):
        """Apply a shape to a DM channel.

        Parameters
        ----------
        channel : str
            The channel to apply the shape to.
        dm_shape : ndarray
            Either a DM command or DM maps.
        """
        # Make sure the command is a Numpy array.
        command = np.array(dm_shape, copy=False)

        # If we're given a DM map, convert it to a command.
        if command.shape != (self.command_length,):
            command = self.dm_maps_to_command(command)

        # Submit the command to the channel.
        getattr(self, channel).submit_data(command)

    def write_dm_shape(self, fname, dm_shape):
        '''Write a DM shape to a file.

        Parameters
        ----------
        fname : str
            The path where to write the DM shape.
        dm_shape : ndarray
            Either a DM command or DM maps.
        '''
        # If we're given a DM map, convert it to a command.
        if dm_shape.shape != (self.command_length,):
            command = self.dm_maps_to_command(dm_shape)
            dm_map = dm_shape
        else:
            command = dm_shape
            dm_map = self.command_to_dm_maps(dm_shape)

        hdus = [
            fits.PrimaryHDU(),
            fits.ImageHDU(dm_map, name='DM_MAP'),
            fits.ImageHDU(command, name='COMMAND')
        ]

        hdu_list = fits.HDUList(hdus)

        hdu_list.writeto(fname)
