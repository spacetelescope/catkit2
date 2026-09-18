from catkit2.base_services.deformable_mirror import DeformableMirrorService
from catkit2.testbed.tracing import trace_interval

import numpy as np
from astropy.io import fits

from alpao.asdk import DM


class AlpaoDeformableMirror(DeformableMirrorService):
    def __init__(self, service_type='alpao_deformable_mirror'):
        super().__init__(service_type)

        self.device_command_index = self.config.get('device_command_index', 0)

        if not isinstance(self.device_command_index, list):
            self.device_command_index = [self.device_command_index]

    def open(self):
        self.device = DM(self.serial_name)
        if not self.device.Check():
            raise RuntimeError(f'Could not connect to DM {self.serial_name}')

        self.device_command_length = int(self.device.Get('NBOfActuator'))

    def close(self):
        try:
            super().close()
        finally:
            self.device.Reset()
            self.device = None

    def send_to_device(self):
        # Convert to hardware command format
        device_command = self.dm_command_to_device_command(self.voltages)

        with trace_interval('send data'):
            # Send the voltages to the DM.
            status = self.device.Send(device_command)

            if status != 0:
                raise RuntimeError(f'Failed to send data: {self.device.error_string(status)}.')

    def dm_command_to_device_command(self, dm_command):
        device_command = np.zeros(self.device_command_length)

        # Check if this service controls more than one DM
        for i, index in enumerate(self.device_command_index):
            # Extract the DM command for this DM
            # and put into correct array slice of device command
            device_command[index:index + self.num_actuators] = dm_command[i * self.num_actuators:(i + 1) * self.num_actuators]

        return device_command


if __name__ == '__main__':
    service = AlpaoDeformableMirror()
    service.run()
