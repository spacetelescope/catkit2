from catkit2.base_services.deformable_mirror import DeformableMirrorService
from catkit2.testbed.tracing import trace_interval

import numpy as np
from astropy.io import fits

from alpao.asdk import DM


class AlpaoDeformableMirror(DeformableMirrorService):
    def __init__(self, service_type='alpao_deformable_mirror'):
        super().__init__(service_type)

        self.serial_name = self.config['serial_name']

        self.device_id = self.config.get('device_id', 0)
        self.flat_map_fname = self.config['flat_map_fname']
        self.gain_map_fname = self.config['gain_map_fname']
        self.max_volts = self.config['max_volts']
        self.dac_bit_depth = self.config['dac_bit_depth']

        self._surface = None
        self._voltages = None
        self._discretized_voltages = None
        self._discretized_surface = None

        self.device_command_index = self.config.get('device_command_index', 0)

        if not isinstance(self.device_command_index, list):
            self.device_command_index = [self.device_command_index]

    def open(self):
        self.device = DM(self.serial_name)
        if not self.device.Check():
            raise RuntimeError(f'Could not connect to DM {self.serial_name}')
        
        self.device_command_length = int(self.device.Get('NBOfActuator'))

        with fits.open(self.flat_map_fname) as f:
            self.flat_map = f['COMMAND'].data.astype('float64')

        if self.gain_map_fname is not None:
            with fits.open(self.gain_map_fname) as f:
                self.gain_map = f['COMMAND'].data.astype('float64')
        else:
            self.gain_map = np.ones(self.device_command_length)

        with np.errstate(divide='ignore', invalid='ignore'):
            self.gain_map_inv = 1 / self.gain_map
            self.gain_map_inv[np.abs(self.gain_map) < 1e-10] = 0

        self.send_surface(np.zeros(self.num_actuators * self.num_dms, dtype='float64'))

        super().open()

    def close(self):
        try:
            super().close()
            self.send_surface(np.zeros(self.num_actuators * self.num_dms, dtype='float64'))
        finally:
            self.device.Reset()
            self.device = None

    def send_surface(self, surface):
        '''Send a surface map to the DM(s).

        Parameters
        ----------
        surface : ndarray
            The requested surface of the DM(s).
        '''
        with trace_interval('send surface'):
            self.surface = surface

            # Send voltages to the device.
            self.send_to_device()

            with trace_interval('compute voltage'):
                discretized_surface = self.discretized_surface
                discretized_voltages = self.discretized_voltages

            # Submit discretized surface and voltages to data streams.
            self.total_surface.submit_data(discretized_surface)
            self.total_voltage.submit_data(discretized_voltages)

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
            voltages = self.surface * self.gain_map_inv
            voltages /= self.max_volts
            voltages += self.flat_map
            voltages -= np.mean(voltages)
            self._voltages = np.clip(voltages, -1, 1)

        return self._voltages

    @voltages.setter
    def voltages(self, voltages):
        self._voltages = np.clip(voltages, -1, 1)
        self._surface = (self._voltages - self.flat_map) * self.max_volts * self.gain_map

        self._discretized_surface = None
        self._discretized_voltages = None

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
                self._discretized_surface = (self.discretized_voltages * self.max_volts - self.flat_map) * self.gain_map

        return self._discretized_surface


if __name__ == '__main__':
    service = AlpaoDeformableMirror()
    service.run()
