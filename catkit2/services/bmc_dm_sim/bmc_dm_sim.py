from catkit2.protocol.service import Service, parse_service_args
from catkit2.simulator.simulated_service import SimulatorClient

import time
import sys
import threading
import numpy as np

class BmcDmSim(Service):
    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'bmc_dm_sim', testbed_port)

        config = self.configuration

        self.serial_number = config['serial_number']
        self.command_length = config['command_length']
        self.flat_map_fname = config['flat_map_fname']
        self.gain_map_fname = config['gain_map_fname']

        self.flat_map = np.zeros(self.command_length)
        self.gain_map = np.ones(self.command_length)

        self.lock = threading.Lock()
        self.shutdown_flag = False

        self.channels = {}
        self.channel_threads = {}
        for channel in config['channels']:
            self.add_channel(channel)

        channel_names = [key.lower() for key in config['channels']]
        self.make_property('channels', lambda: channel_names)

        self.total_voltage = self.make_data_stream('total_voltage', 'float64', [self.command_length], 20)
        self.total_surface = self.make_data_stream('total_surface', 'float64', [self.command_length], 20)

        self.simulator_connection = SimulatorClient(service_name, testbed_port)

    def add_channel(self, channel_name):
        self.channels[channel_name] = self.make_data_stream(channel_name, 'float64', [self.command_length], 20)

        # Zero-out the channel.
        frame = self.channels[channel_name].submit_data(np.zeros(self.command_length))

    def main(self):
        # Start channel monitoring threads
        for channel_name in self.channels.keys():
            self.channel_threads[channel_name] = threading.Thread(target=self.monitor_channel, args=(channel_name,))

        while not self.shutdown_flag:
            time.sleep(0.01)

        for thread in self.channel_threads.values():
            thread.join()
        self.channel_threads = {}

    def shut_down(self):
        self.shutdown_flag = True

    def monitor_channel(self, channel_name):
        while not self.shutdown_flag:
            try:
                frame = self.channels[channel_name].get_next_frame(10)
            except:
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
        voltages = self.flat_map + total_surface * self.gain_map

        with self.lock:
            self.simulator_connection.actuate_dm(-1, self.name, voltages)

        # Submit these voltages to the total voltage data stream.
        self.total_voltage.submit_data(voltages)

    def open(self):
        zeros = np.zeros(self.command_length, dtype='float64')
        self.send_surface(zeros)

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = BmcDmSim(service_name, testbed_port)
    service.run()
