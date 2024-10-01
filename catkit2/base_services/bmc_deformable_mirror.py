from catkit2.base_services.deformable_mirror import DeformableMirrorService

import numpy as np
from astropy.io import fits


class BmcDeformableMirror(DeformableMirrorService):
    def __init__(self, service_type):
        super().__init__(service_type)

        self.serial_number = self.config['serial_number']
        self.flat_map_fname = self.config['flat_map_fname']
        self.gain_map_fname = self.config['gain_map_fname']
        self.max_volts = self.config['max_volts']
        self.dac_bit_depth = self.config['dac_bit_depth']

        self._surface = None
        self._voltages = None
        self._discretized_voltages = None
        self._discretized_surface = None

    def open(self):
        super().open()

        with fits.open(self.flat_map_fname) as f:
            self.flat_map = f['COMMAND'].data.astype('float64')

        with fits.open(self.gain_map_fname) as f:
            self.gain_map = f['COMMAND'].data.astype('float64')

        with np.errstate(divide='ignore', invalid='ignore'):
            self.gain_map_inv = 1 / self.gain_map
            self.gain_map_inv[np.abs(self.gain_map) < 1e-10] = 0

        self.send_surface(np.zeros(self.num_actuators * self.num_dms, dtype='float64'))

    def close(self):
        super().close()

        self.send_surface(np.zeros(self.num_actuators * self.num_dms, dtype='float64'))

    def send_surface(self, surface):
        '''Send a surface map to the DM(s).

        Parameters
        ----------
        surface : ndarray
            The requested surface of the DM(s).
        '''
        self.surface = surface

        # Send voltages to the device.
        self.send_to_device()

        # Submit discretized surface and voltages to data streams.
        self.total_surface.submit_data(self.discretized_surface)
        self.total_voltage.submit_data(self.discretized_voltages)

    def send_to_device(self):
        '''Send the surface to the simulated/real hardware.

        This can be either self.surface or self.voltages.
        '''
        raise NotImplementedError('send_to_device() should be implemented by subclasses.')

    @property
    def surface(self):
        return self._surface

    @surface.setter
    def surface(self, surface):
        self._surface = surface

        self._voltages = None
        self._discretized_surface = None
        self._discretized_voltages = None

    @property
    def voltages(self):
        if self._voltages is None:
            # Compute the voltages from the requested total surface.
            voltages = self.flat_map_command + self.surface * self.gain_map_inv_command
            voltages /= self.max_volts
            self._voltages = np.clip(voltages, 0, 1)

        return self._voltages

    @property
    def discretized_voltages(self):
        if self._discretized_voltages is None:
            self._discretized_voltages = self.voltages

            if self.dac_bit_depth is not None:
                self._discretized_voltages = (np.floor(self.voltages * (2**self.dac_bit_depth))) / (2**self.dac_bit_depth)

        return self._discretized_voltages

    @property
    def discretized_surface(self):
        if self._discretized_surface is None:
            self._discretized_surface = self.surface

            if self.dac_bit_depth is not None:
                self._discretized_surface = (self.discretized_voltages * self.max_volts - self.flat_map_command) * self.gain_map_command

        return self._discretized_surface
