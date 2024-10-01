from catkit2.base_services.bmc_deformable_mirror import BmcDeformableMirror

import threading
import sys
import os
import numpy as np

try:
    sdk_path = os.environ.get('CATKIT_BOSTON_SDK_PATH')
    if sdk_path is not None:
        sys.path.append(sdk_path)

    import bmc
except ImportError:
    print('To use Boston DMs, you need to set the CATKIT_BOSTON_SDK_PATH environment variable.')
    raise


class BmcDeformableMirrorHardware(BmcDeformableMirror):
    def __init__(self):
        super().__init__('bmc_deformable_mirror_hardware')

        self.device_command_index = self.config.get('device_command_index', 0)

        self.lock = threading.Lock()

    def open(self):
        super().open()

        self.device = bmc.BmcDm()
        status = self.device.open_dm(self.serial_number)

        if status != bmc.NO_ERR:
            raise RuntimeError(f'Failed to connect: {self.dm.error_string(status)}.')

        self.device_command_length = self.device.num_actuators()

        zeros = np.zeros(self.num_actuators * self.num_dms, dtype='float64')
        self.send_surface(zeros)

    def close(self):
        try:
            zeros = np.zeros(self.num_actuators * self.num_dms, dtype='float64')
            self.send_surface(zeros)
        finally:
            self.device.close_dm()
            self.device = None

        super().close()

    def send_to_device(self):
        # Convert to hardware command format
        device_command = self.dm_command_to_device_command(self.voltages)

        with self.lock:
            # Send the voltages to the DM.
            status = self.device.send_data(device_command)

            if status != bmc.NO_ERR:
                raise RuntimeError(f'Failed to send data: {self.device.error_string(status)}.')

    def dm_command_to_device_command(self, dm_command):
        device_command = np.zeros(self.device_command_length)

        # Check if this service controls more than one DM
        if isinstance(self.device_command_index, list):
            for index in self.device_command_index:
                # Extract the DM command for this DM
                # and put into correct array slice of device command
                device_command[index:] = dm_command[:self.num_actuators]

                # Remove the DM command that has been applied
                dm_command = dm_command[self.num_actuators:]
        else:
            dm_command_length = dm_command.shape[0]
            try:
                device_command[self.device_command_index:self.device_command_index + dm_command_length] = dm_command
            except ValueError:
                raise ValueError(f'Invalid device command index: {self.device_command_index} for command length: {dm_command_length} with device command length: {self.device_command_length}.')

        return device_command


if __name__ == '__main__':
    service = BmcDeformableMirrorHardware()
    service.run()
