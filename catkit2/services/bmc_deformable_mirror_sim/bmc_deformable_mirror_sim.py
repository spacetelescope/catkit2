from catkit2.base_services.deformable_mirror import DeformableMirrorService

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
        self.dac_bit_depth = self.config['dac_bit_depth']
        self._discretized_voltages = None
        self._discretized_surface = None

        device_actuators = np.count(self.device_actuator_mask)  # TODO: is np.count() correct here?
        self.flat_map = np.zeros(device_actuators)
        self.gain_map = np.zeros(device_actuators)
        self.gain_map_inv = np.zeros(device_actuators)  # TODO: Why is these initializations not needed in the hardware service?

        self.lock = threading.Lock()

    def open(self):
        super().open()

        self.flat_map = fits.getdata(self.flat_map_fname)  # TODO: concatenate into a single 1D array here; later will need to ravel when we make them a cube
        self.gain_map = fits.getdata(self.gain_map_fname)  # TODO: see above

        with np.errstate(divide='ignore', invalid='ignore'):
            self.gain_map_inv = 1 / self.gain_map  # TODO: will this remain true with concatenated gain maps?
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
        self.discretized_surface = total_surface

        with self.lock:
            self.testbed.simulator.actuate_dm(dm_name=self.id, new_actuators=self.discretized_surface)

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


if __name__ == '__main__':
    service = BmcDeformableMirrorSim()
    service.run()
