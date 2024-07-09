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

        self.flat_map_command = np.zeros(self.num_actuators * self.num_dms)
        self.gain_map_command = np.zeros(self.num_actuators * self.num_dms)
        self.gain_map_inv_command = np.zeros(self.num_actuators * self.num_dms)  # TODO: Why are these initializations not needed in the hardware service?

        self.lock = threading.Lock()

    def open(self):
        super().open()

        self.flat_map = fits.getdata(self.flat_map_fname)
        if self.flat_map.ndim <= 1:
            raise ValueError(f'The provided flat map for {self.service_id} needs to be at least a 2D array.')
        elif self.flat_map.ndim == 2:
            self.flat_map = np.expand_dims(self.flat_map, axis=0)
        # Convert to DM command
        self.flat_map_command = self.flat_map[self.device_actuator_mask]

        self.gain_map = fits.getdata(self.gain_map_fname)
        if self.gain_map.ndim <= 1:
            raise ValueError(f'The provided gain map for {self.service_id} needs to be at least a 2D array.')
        elif self.gain_map.ndim == 2:
            self.gain_map = np.expand_dims(self.gain_map, axis=0)
        # Convert to DM command
        self.gain_map_command = self.gain_map[self.device_actuator_mask]

        with np.errstate(divide='ignore', invalid='ignore'):
            self.gain_map_inv_command = np.ones_like(self.gain_map_command)
            self.gain_map_inv_command = 1 / self.gain_map_command    # TODO: Is this still correct?
            self.gain_map_inv_command[np.abs(self.gain_map_command) < 1e-10] = 0

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

    def send_surface(self, total_surface):
        # Compute the voltages from the requested total surface.
        voltages = self.flat_map_command + total_surface * self.gain_map_inv_command
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
            values = (self.discretized_voltages * self.max_volts - self.flat_map_command) * self.gain_map_command
        self._discretized_surface = values


if __name__ == '__main__':
    service = BmcDeformableMirrorSim()
    service.run()
