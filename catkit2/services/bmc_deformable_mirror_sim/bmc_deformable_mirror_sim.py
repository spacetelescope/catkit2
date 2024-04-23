from catkit2.base_services.deformable_mirror import DeformableMirrorService

import time
import sys
import os
import threading
import numpy as np
from astropy.io import fits


class BmcDeformableMirrorSim(DeformableMirrorService):
    def __init__(self):
        super().__init__('bmc_deformable_mirror_sim')

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
        discretized_surface = total_surface
        if dac_bit_depth is not None:
            discretized_surface = (self.discretized_voltages * self.max_volts - self.flat_map) * self.gain_map

        with self.lock:
            self.testbed.simulator.actuate_dm(dm_name=self.id, new_actuators=discretized_surface)

        super().send_surface(total_surface)


if __name__ == '__main__':
    service = BmcDeformableMirrorSim()
    service.run()
