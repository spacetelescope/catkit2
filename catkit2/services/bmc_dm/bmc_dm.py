from catkit2.testbed.service import Service

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

class BmcDm(Service):
    def __init__(self):
        super().__init__('bmc_dm')

        self.serial_number = self.config['serial_number']
        self.command_length = self.config['command_length']
        self.flat_map_fname = self.config['flat_map_fname']
        self.gain_map_fname = self.config['gain_map_fname']
        self.max_volts = self.config['max_volts']

        self.startup_maps = self.config.get('startup_maps', {})

        self.lock = threading.Lock()

        self.channels = {}
        self.channel_threads = {}
        for channel in self.config['channels']:
            self.add_channel(channel)

        channel_names = list(channel.lower() for channel in self.config['channels'])
        self.make_property('channels', lambda: channel_names)

        self.total_voltage = self.make_data_stream('total_voltage', 'float64', [self.command_length], 20)
        self.total_surface = self.make_data_stream('total_surface', 'float64', [self.command_length], 20)

    def add_channel(self, channel_name):
        self.channels[channel_name] = self.make_data_stream(channel_name.lower(), 'float64', [self.command_length], 20)

        # Get the right default flat map.
        if channel_name in self.startup_maps:
            flatmap = fits.getdata(self.startup_maps[channel_name]).astype('float64')
        else:
            flatmap = np.zeros(self.command_length)

        self.channels[channel_name].submit_data(flatmap)

    def main(self):
        self.channel_threads = {}

        # Start channel monitoring threads
        for channel_name in self.channels.keys():
            thread = threading.Thread(target=self.monitor_channel, args=(channel_name,))
            thread.start()

            self.channel_threads[channel_name] = thread

        while not self.should_shut_down:
            time.sleep(0.01)

        for thread in self.channel_threads.values():
            thread.join()
        self.channel_threads = {}

    def monitor_channel(self, channel_name):
        while not self.should_shut_down:
            try:
                self.channels[channel_name].get_next_frame(10)
            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            self.update_dm()

    def update_dm(self):
        # Add up all channels to get the total surface.
        total_surface = 0
        for stream in self.channels.values():
            total_surface += stream.get_latest_frame().data

        # Apply the command on the DM.
        self.send_surface(total_surface)

    def send_surface(self, total_surface):
        # Submit this surface to the total surface data stream.
        self.total_surface.submit_data(total_surface)

        # Compute the voltages from the request total surface.
        voltages = self.flat_map + total_surface * self.gain_map_inv
        voltages /= self.max_volts

        voltages = np.clip(voltages, 0, 1)

        dac_bit_depth = self.config['dac_bit_depth']
        discretized_voltages = (np.floor(voltages * (2**dac_bit_depth))) / (2**dac_bit_depth)

        with self.lock:
            status = self.device.send_data(voltages)

            if status != bmc.NO_ERR:
                raise RuntimeError(f'Failed to send data: {self.device.error_string(status)}.')

        # Submit these voltages to the total voltage data stream.
        self.total_voltage.submit_data(discretized_voltages)

    def open(self):
        self.flat_map = fits.getdata(self.flat_map_fname)
        self.gain_map = fits.getdata(self.gain_map_fname)

        with np.errstate(divide='ignore', invalid='ignore'):
            self.gain_map_inv = 1 / self.gain_map
            self.gain_map_inv[np.abs(self.gain_map) < 1e-10] = 0

        self.device = bmc.BmcDm()
        status = self.device.open_dm(self.serial_number)

        if status != bmc.NO_ERR:
            raise RuntimeError(f'Failed to connect: {self.dm.error_string(status)}.')

        command_length = self.device.num_actuators()
        if self.command_length != command_length:
            raise ValueError(f'Command length in config: {self.command_length}. Command length on hardware: {command_length}.')

        zeros = np.zeros(self.command_length, dtype='float64')
        self.send_surface(zeros)

    def close(self):
        try:
            zeros = np.zeros(self.command_length, dtype='float64')
            self.send_surface(zeros)
        finally:
            self.device.close_dm()
            self.device = None

if __name__ == '__main__':
    service = BmcDm()
    service.run()
