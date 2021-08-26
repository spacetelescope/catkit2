from hicat2.bindings import Module, DataStream, Command, Property
from hicat2.testbed import parse_module_args

import time
import sys
import threading

sdk_path = os.environ.get('CATKIT_BOSTON_SDK_PATH')
if sdk_path is not None:
    sys.path.append(sdk_path)

import bmc

class BmcDmModule(Module):
    def __init__(self):
        args = parse_module_args()
        Module.__init__(self, args.module_name, args.module_port)

        testbed = Testbed(args.testbed_server_port)
        config = testbed.config['modules'][args.module_name]

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

        self.total_voltage = DataStream.create('total_voltage', self.name, 'float64', [self.command_length], 20)
        self.register_data_stream(self.total_voltage)

        self.total_surface = DataStream.create('total_surface', self.name, 'float64', [self.command_length], 20)
        self.register_data_stream(self.total_surface)

    def add_channel(self, channel_name):
        self.channels[channel_name] = DataStream.create('channel_' + channel_name, self.name, 'float64', [self.command_length], 20)
        self.register_data_steam(self.channels[channel_name])

        frame = self.channels[channel_name].request_new_frame()
        frame.data[:] = 0
        self.channels[channel_name].submit_frame(frame.id)

    def main(self):
        self.open()

        # Start channel monitoring threads
        for channel_name in self.channels.keys():
            self.channel_threads = threading.Thread(target=self.monitor_channel, args=(channel_name,))

        while not self.shutdown_flag:
            time.sleep(0.01)

        for thread in self.channel_threads:
            thread.join()

        self.close()

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

        # Submit a frame to the total surface data stream.
        frame = self.total_surface.request_new_frame()
        frame.data[:] = total_surface
        self.total_surface.submit_frame(frame.id)

        # Compute the voltages from the request total surface.
        voltages = self.flat_map + total_surface * self.gain_map

        # Apply the command on the DM.
        self.send_data(total_surface)

    def send_data(self, data):
        with self.lock:
            status = self.device.send_data(total_command)

            if status != bmc.NO_ERR:
                raise RuntimeError(f'Failed to send data: {self.device.error_string(status)}.')

        # Submit a frame to the total voltage data stream.
        frame = self.total_voltage.request_new_frame()
        frame.data[:] = data
        self.total_surface.submit_frame(frame.id)

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

def main():
    module = ThorlabsMFF101Module()
    module.run()

if __name__ == '__main__':
    main()
