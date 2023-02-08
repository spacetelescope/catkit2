from catkit2.testbed.service import Service

import numpy as np
import threading

import nidaqmx

class NiDaq(Service):
    def __init__(self):
        super().__init__('ni_daq')

        self.lock = threading.Lock()

        self.channels = {}
        self.channel_threads = {}

    def open(self):
        # Make sure our DAQ device is connected.
        self.device_name = self.config['device_name']

        system = nidaqmx.system.System.local()
        for device in system.devices:
            if self.device_name == device.name:
                break
        else:
            raise RuntimeError(f'Device {self.device_name} is not connected.')

        # Create a task.
        self.task = nidaqmx.Task()

        # Add all requested channels.
        self.input_channels = self.config['daq_input_channels']

        for channel in self.input_channels:
            channel_name = self.device_name + '/' + channel
            self.task.ai_channels.add_ao_voltage_chan(channel_name)

        self.output_channels = self.config['daq_output_channels']

        for channel in self.output_channels:
            channel_name = self.device_name + '/' + channel
            self.task.ai_channels.add_ao_voltage_chan(channel_name)

        self.command_length = len(self.output_channels)

        # Start the task so that it does not restart every time a sample is written.
        self.task.start()

        # Read in voltage limits.
        self.volt_limit_min = self.config['volt_limit_min']
        self.volt_limit_max = self.config['volt_limit_max']

        # Create DM channels.
        self.channels = {}

        for channel in self.config['channels']:
            self.add_channel(channel)

        self.total_voltage = self.make_data_stream('total_voltage', 'float64', [self.command_length], 20)

        # Start channel monitoring threads
        self.channel_threads = {}

        for channel_name in self.channels.keys():
            thread = threading.Thread(target=self.monitor_channel, args=(channel_name,))
            thread.start()

            self.channel_threads[channel_name] = thread

    def add_channel(self, channel_name):
        self.channels[channel_name] = self.make_data_stream(channel_name.lower(), 'float64', [self.command_length], 20)

        self.channels[channel_name].submit_data(np.zeros(self.command_length))

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        # Join all threads.
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

            self.update_daq()

    def update_daq(self):
        # Add up all channels to get the total surface.
        total_voltage = 0
        for stream in self.channels.values():
            total_voltage += stream.get_latest_frame().data

        # Apply the command on the DAQ.
        self.write_multichannel(total_voltage)

        # Submit these voltages to the total voltage data stream.
        self.total_voltage.submit_data(total_voltage)

    def read_multichannel(self):
        '''Read voltages from all configured input channels.

        Returns
        -------
        ndarray
            The voltages for each of the channels.
        '''
        return self.task.read()

    def write_multichannel(self, values):
        '''Write voltages to all configured output channels.

        Parameters
        ----------
        values : ndarray
            An array containing the voltages for each channel.

        Raises
        ------
        ValueError
            In case the number of elements in `values` is not correct.
        '''
        if len(values) != len(self.output_channels):
            raise ValueError(f'The values should have the same length as the number of output channels ({len(self.output_channels)}) .')

        if (np.max(values) > self.volt_limit_max) or (np.min(values) < self.volt_limit_min):
            self.log.warning('Voltage values will be clipped as they are larger than the allowed voltage limits.')
            self.log.warning(f'Min voltage: {np.min(values)} V; max voltage: {np.max(values)} V.')
            self.log.warning(f'Voltage limits: {self.volt_limit_min} V < voltage < {self.volt_limit_max} V.')

        values = np.clip(self.volt_limit_min, self.volt_limit_max, values)

        self.task.write(values)
