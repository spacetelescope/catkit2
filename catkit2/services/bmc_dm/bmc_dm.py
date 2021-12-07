from catkit2.protocol.service import Service, parse_service_args

import time
import sys
import threading

sdk_path = os.environ.get('CATKIT_BOSTON_SDK_PATH')
if sdk_path is not None:
    sys.path.append(sdk_path)

import bmc

class BmcDm(Service):
    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'bmc_dm', testbed_port)

        config = self.configuration

        self.serial_number = config['serial_number']
        self.command_length = config['command_length']
        self.flat_map_fname = config['flat_map_fname']
        self.gain_map_fname = config['gain_map_fname']

        self.lock = threading.Lock()
        self.shutdown_flag = False

        self.channels = {}
        self.channel_threads = {}
        for channel in config['channels']:
            self.add_channel(channel)

        self.total_voltage = self.make_data_stream('total_voltage', 'float64', [self.command_length], 20)
        self.total_surface = self.make_data_stream('total_surface', 'float64', [self.command_length], 20)

    def add_channel(self, channel_name):
        self.channels[channel_name] = self.make_data_stream('channel_' + channel_name, 'float64', [self.command_length], 20)

        # Zero-out the channel.
        frame = self.channels[channel_name].submit_data(np.zeros(command_length))

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

        # Submit this surface to the total surface data stream.
        self.total_surface.submit_data(total_surface)

        # Apply the command on the DM.
        self.send_surface(total_surface)

    def send_surface(self, data):
        # Compute the voltages from the request total surface.
        voltages = self.flat_map + total_surface * self.gain_map

        with self.lock:
            status = self.device.send_data(total_command)

            if status != bmc.NO_ERR:
                raise RuntimeError(f'Failed to send data: {self.device.error_string(status)}.')

        # Submit these voltages to the total voltage data stream.
        self.total_voltage.submit_data(data)

    def open(self):
        self.device = bmc.BmcDm()
        status = self.device.open_dm(self.serial_number)

        if status != bmc.NO_ERR:
            raise RuntimeError(f'Failed to connect: {self.dm.error_string(status)}.')

        command_length = dm.num_actuators()
        if self.command_length != command_length:
            raise ValueError(f'Command length in config: {self.command_length}. Command length on hardware: {command_length}.')

        zeros = np.zeros(self.command_length, dtype='float64')
        self.send_data(zeros)

    def close(self):
        try:
            zeros = np.zeros(self.command_length, dtype='float64')
            self.send_data(zeros)
        finally:
            self.device.close_dm()
            self.device = None

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = BmcDm(service_name, testbed_port)
    service.run()
