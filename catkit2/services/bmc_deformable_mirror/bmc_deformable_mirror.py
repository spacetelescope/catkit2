from catkit2.base_services.deformable_mirror import DeformableMirrorService

import sys
import os
import threading
import numpy as np
from astropy.io import fits

try:
    sdk_path = os.environ.get('CATKIT_BOSTON_SDK_PATH')
    if sdk_path is not None:
        sys.path.append(sdk_path)

    import bmc
except ImportError:
    print('To use Boston DMs, you need to set the CATKIT_BOSTON_SDK_PATH environment variable.')
    raise


class BmcDeformableMirror(DeformableMirrorService):
    def __init__(self):
        super().__init__('bmc_deformable_mirror')

        self.serial_number = self.config['serial_number']
        self.flat_map_fname = self.config['flat_map_fname']
        self.gain_map_fname = self.config['gain_map_fname']
        self.max_volts = self.config['max_volts']

        self.dac_bit_depth = self.config['dac_bit_depth']
        self._discretized_voltages = None
        self._discretized_surface = None

        self.device_command_index = self.config.get('device_command_index', 0)

        # Check if this service controls more than one DM and get the number of actuators controlled by each DM
        if isinstance(self.device_command_index, list):
            self.dm_num_actuators = []
            for i, index in enumerate(self.device_command_index):
                # Get the number of actuators controlled by this DM
                self.dm_num_actuators.append(np.sum(self.device_actuator_mask[i]))  # TODO: Uses assumption that device actuator masks are stacked in some way
        else:
            self.dm_num_actuators = None

        self.lock = threading.Lock()

    def open(self):
        super().open()

        self.flat_map = fits.getdata(self.flat_map_fname)
        self.gain_map = fits.getdata(self.gain_map_fname)

        with np.errstate(divide='ignore', invalid='ignore'):
            self.gain_map_inv = 1 / self.gain_map
            self.gain_map_inv[np.abs(self.gain_map) < 1e-10] = 0

        self.device = bmc.BmcDm()
        status = self.device.open_dm(self.serial_number)

        if status != bmc.NO_ERR:
            raise RuntimeError(f'Failed to connect: {self.dm.error_string(status)}.')

        self.device_command_length = self.device.num_actuators()

        zeros = np.zeros(self.num_actuators, dtype='float64')
        self.send_surface(zeros)

    def close(self):
        try:
            zeros = np.zeros(self.num_actuators, dtype='float64')
            self.send_surface(zeros)
        finally:
            self.device.close_dm()
            self.device = None

        super().close()

    def send_surface(self, total_surface):
        # Compute the voltages from the requested total surface.
        voltages = self.flat_map + total_surface * self.gain_map_inv
        voltages /= self.max_volts
        voltages = np.clip(voltages, 0, 1)

        self.discretized_voltages = voltages
        self.discretized_surface = total_surface

        # Convert to hardware command format
        device_command = self.dm_command_to_device_command(self.discretized_voltages)

        with self.lock:
            # Send the voltages to the DM.
            status = self.device.send_data(device_command)

            if status != bmc.NO_ERR:
                raise RuntimeError(f'Failed to send data: {self.device.error_string(status)}.')

        # Submit discretized surface and voltages to data streams.
        self.total_surface.submit_data(self.discretized_surface)
        self.total_voltage.submit_data(self.discretized_voltages)

    @property
    def discretized_voltages(self):
        return self._discretized_voltages

    @discretized_voltages.setter
    def discretized_voltages(self, voltages):
        values = voltages
        if self.dac_bit_depth is not None:
            values = (np.floor(voltages * (2**self.dac_bit_depth))) / (2**self.dac_bit_depth)
        self._discretized_voltages = values

    @property
    def discretized_surface(self):
        return self._discretized_surface

    @discretized_surface.setter
    def discretized_surface(self, total_surface):
        values = total_surface
        if self.dac_bit_depth is not None:
            values = (self.discretized_voltages * self.max_volts - self.flat_map) * self.gain_map
        self._discretized_surface = values

    def dm_command_to_device_command(self, dm_command):
        device_command = np.zeros(self.device_command_length)

        # Check if this service controls more than one DM
        if isinstance(self.device_command_index, list):
            for i, index in enumerate(self.device_command_index):
                # Extract the DM command for this DM
                this_dm_command = dm_command[:self.dm_num_actuators[i]]
                # Put this DM command into correct array slice of device command
                device_command[index:] = this_dm_command

                # Remove the DM command that has been applied
                dm_command = dm_command[self.dm_num_actuators[i]:]
        else:
            dm_command_length = dm_command.shape[0]
            try:
                device_command[self.device_command_index:self.device_command_index + dm_command_length] = dm_command
            except ValueError:
                raise ValueError(f'Invalid device command index: {self.device_command_index} for command length: {dm_command_length}.')

        return device_command


if __name__ == '__main__':
    service = BmcDeformableMirror()
    service.run()
