from catkit2.testbed.service import Service

from dcps import AimTTiPLP
import threading
import numpy as np


class AimttiPLPDevice(Service):
    def __init__(self):
        super().__init__('aimtti_plp_device')

        self.visa_id = self.config['visa_id']
        self.channels = self.config['channels']

        self.lock_for_voltage = threading.Lock()
        self.lock_for_current = threading.Lock()

        self.voltage_commands = {}
        self.current_commands = {}
        self.measured_voltage = {}
        self.measured_current = {}
        self.stream_threads = {}
        for channel_name in self.channels.keys():
            self.add_channel(channel_name)

    def add_channel(self, channel_name):
        self.voltage_commands[channel_name] = self.make_data_stream(channel_name.lower() + '_voltage_command', 'float32', [1], 20)
        self.current_commands[channel_name] = self.make_data_stream(channel_name.lower() + '_current_command', 'float32', [1], 20)
        self.measured_voltage[channel_name] = self.make_data_stream(channel_name.lower() + '_measured_voltage', 'float32', [1], 20)
        self.measured_current[channel_name] = self.make_data_stream(channel_name.lower() + '_measured_current', 'float32', [1], 20)

    def open(self):
        self.device = AimTTiPLP(self.visa_id)
        self.device.open()

        for channel_name in self.channels.keys():
            if not self.device.isOutputOn(self.channels[channel_name]['channel_number']):
                self.device.outputOn(self.channels[channel_name]['channel_number'])

        self.make_command('query_commanded_voltage', self.query_commanded_voltage)
        self.make_command('query_commanded_current', self.query_commanded_current)
        self.make_command('set_over_voltage_protection', self.set_over_voltage_protection)
        self.make_command('set_over_current_protection', self.set_over_current_protection)
        self.make_command('reset_trip_conditions', self.reset_trip_conditions)

    def main(self):
        # Start channel monitoring threads
        for channel_name in self.channels.keys():
            thread_voltage = threading.Thread(target=self.monitor_voltage_command, args=(channel_name,))
            thread_voltage.start()

            self.stream_threads[channel_name + '_voltage'] = thread_voltage

            thread_current = threading.Thread(target=self.monitor_current_command, args=(channel_name,))
            thread_current.start()

            self.stream_threads[channel_name + '_current'] = thread_current

        while not self.should_shut_down:
            for channel_name in self.channels.keys():
                self.measure_voltage(channel_name)
                self.measure_current(channel_name)

            self.sleep(0.01)

    def monitor_voltage_command(self, channel_name):
        while not self.should_shut_down:
            try:
                # Get an update for this channel
                frame = self.voltage_commands[channel_name].get_next_frame(10)
                value = frame.data[0]

                # Update the device
                self.set_voltage(channel_name, value)

            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def monitor_current_command(self, channel_name):
        while not self.should_shut_down:
            try:
                # Get an update for this channel
                frame = self.current_commands[channel_name].get_next_frame(10)
                value = frame.data[0]

                # Update the device
                self.set_current(channel_name, value)

            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def close(self):
        for thread in self.stream_threads.values():
            thread.join()
        self.stream_threads = {}

        for channel_name in self.channels.keys():
            self.set_voltage(channel_name, value=0)
            self.set_current(channel_name, value=0)
            self.device.outputOff(self.channels[channel_name]['channel_number'])

        self.device.close()

    def measure_voltage(self, channel_name):
        """Measure the voltage of a channel."""
        channel_number = self.channels[channel_name]['channel_number']
        with self.lock_for_voltage:
            measured_voltage = self.device.measureVoltage(channel=channel_number)

        # Update measured voltage data stream.
        stream = self.measured_voltage[channel_name]
        stream.submit_data(np.array([measured_voltage]).astype('float32'))

    def measure_current(self, channel_name):
        """Measure the current of a channel."""
        channel_number = self.channels[channel_name]['channel_number']
        with self.lock_for_current:
            measured_current = self.device.measureCurrent(channel=channel_number)

        # Update measured current data stream.
        stream = self.measured_current[channel_name]
        stream.submit_data(np.array([measured_current]).astype('float32'))

    def set_voltage(self, channel_name, value):
        """Set output voltage for a channel."""
        channel_number = self.channels[channel_name]['channel_number']
        with self.lock_for_voltage:
            self.device.setVoltage(voltage=value, channel=channel_number)

    def set_current(self, channel_name, value):
        """Set output current limit for a channel."""
        channel_number = self.channels[channel_name]['channel_number']
        with self.lock_for_current:
            self.device.setCurrent(current=value, channel=channel_number)

    def query_commanded_voltage(self, channel_name):
        """Return set voltage of output for a channel (not the measured voltage)."""
        channel_number = self.channels[channel_name]['channel_number']

        return self.device.queryVoltage(channel=channel_number)

    def query_commanded_current(self, channel_name):
        """Return set current limit of output for a channel (not the measured current)."""
        channel_number = self.channels[channel_name]['channel_number']

        return self.device.queryCurrent(channel=channel_number)

    def set_over_voltage_protection(self, channel_name, value):
        """Set over voltage protection trip point for a channel."""
        channel_number = self.channels[channel_name]['channel_number']

        str = 'OVP{} {}'.format(channel_number, value)
        self.device._instWrite(str)

        # Give some time for power supply to respond
        self.sleep(self.device._wait)

    def set_over_current_protection(self, channel_name, value):
        """Set over current protection trip point for a channel."""
        channel_number = self.channels[channel_name]['channel_number']

        str = 'OCP{} {}'.format(channel_number, value)
        self.device._instWrite(str)

        # Give some time for power supply to respond
        self.sleep(self.device._wait)

    def reset_trip_conditions(self):
        """Attempt to clear all trip conditions.

        This only works if the device has not been set up so that it can only reset trip conditions manually on the
        front panel, or by cycling the AC power.
        """
        str = 'TRIPRST'
        self.device._instWrite(str)

        # Give some time for power supply to respond
        self.sleep(self.device._wait)


if __name__ == '__main__':
    service = AimttiPLPDevice()
    service.run()
