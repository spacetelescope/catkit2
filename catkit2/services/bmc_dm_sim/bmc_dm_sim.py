from catkit2.testbed.service import Service
from catkit2.simulator.simulated_service import SimulatorClient

import time
import sys
import threading
import numpy as np
from astropy.io import fits

class BmcDmSim(Service):
    def __init__(self):
        super().__init__('bmc_dm_sim')

        self.serial_number = self.config['serial_number']
        self.command_length = self.config['command_length']
        self.flat_map_fname = self.config['flat_map_fname']
        self.gain_map_fname = self.config['gain_map_fname']
        self.max_volts = self.config['max_volts']

        self.flat_map = np.zeros(self.command_length)
        self.gain_map = np.ones(self.command_length)

        self.lock = threading.Lock()

        self.channels = {}
        self.channel_threads = {}
        for channel in self.config['channels']:
            self.add_channel(channel)

        channel_names = [channel.lower() for channel in self.config['channels']]
        self.make_property('channels', lambda: channel_names)

        self.total_voltage = self.make_data_stream('total_voltage', 'float64', [self.command_length], 20)
        self.total_surface = self.make_data_stream('total_surface', 'float64', [self.command_length], 20)

        # TODO: connect to simulator.

    def add_channel(self, channel_name):
        self.channels[channel_name] = self.make_data_stream(channel_name, 'float64', [self.command_length], 20)

        # Zero-out the channel.
        frame = self.channels[channel_name].submit_data(np.zeros(self.command_length))

    def main(self):
        self.channel_threads = {}

        # Start channel monitoring threads
        for channel_name in self.channels.keys():
            thread = threading.Thread(target=self.monitor_channel, args=(channel_name,))
            thread.start()

            self.channel_threads[channel_name] = thread

        while not self.should_shut_down:
            self.sleep(1)

        for thread in self.channel_threads.values():
            thread.join()
        self.channel_threads = {}

    def monitor_channel(self, channel_name):
        while not self.should_shut_down:
            try:
                frame = self.channels[channel_name].get_next_frame(10)
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

        with self.lock:
            pass#self.simulator_connection.actuate_dm(-1, self.name, voltages)

        # Submit these voltages to the total voltage data stream.
        self.total_voltage.submit_data(voltages)

    def open(self):
        self.flat_map = fits.getdata(self.flat_map_fname)
        self.gain_map = fits.getdata(self.gain_map_fname)

        with np.errstate(divide='ignore', invalid='ignore'):
            self.gain_map_inv = 1 / self.gain_map
            self.gain_map_inv[np.abs(self.gain_map) < 1e-10] = 0

        zeros = np.zeros(self.command_length, dtype='float64')
        self.send_surface(zeros)

if __name__ == '__main__':
    service = BmcDmSim()
    service.run()
