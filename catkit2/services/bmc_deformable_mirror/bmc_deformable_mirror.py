from catkit2.base_services.deformable_mirror_service import DeformableMirrorService

import time
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

        # Convert to hardware command format
        device_command = np.zeros(self.device_command_length)
        device_command[:self.num_actuators] = voltages

        with self.lock:
            # Send the voltages to the DM.
            status = self.device.send_data(device_command)

            if status != bmc.NO_ERR:
                raise RuntimeError(f'Failed to send data: {self.device.error_string(status)}.')

        super().send_surface(total_surface)


if __name__ == '__main__':
    service = BmcDeformableMirror()
    service.run()
