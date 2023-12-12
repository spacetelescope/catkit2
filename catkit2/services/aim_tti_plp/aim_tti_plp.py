from catkit2.testbed.service import Service

from dcps import AimTTiPPL
import threading
import time


class AimTtiPlp(Service):
    def __init__(self):
        super().__init__('aim_tti_plp')

        self.visa_id = self.config['visa_id']
        self.max_voltage = self.config['max_voltage']
        self.max_current = self.config['max_current']

        self.lock = threading.Lock()

        self.voltage_streams = {}
        self.current_streams = {}
        self.stream_threads = {}
        for channel_name in list(self.config['channels']):
            self.add_current_channel(channel_name)
            self.add_voltage_channel(channel_name)

    def add_current_channel(self, channel_name):
        stream = channel_name.lower() + '_current'
        self.current_streams[stream] = self.make_data_stream(stream, 'float32', [1], 20)

    def add_voltage_channel(self, channel_name):
        stream = channel_name.lower() + '_voltage'
        self.voltage_streams[stream] = self.make_data_stream(stream, 'float32', [1], 20)

    def open(self):
        self.device = AimTTiPPL(self.visa_id)
        self.device.open()

        for channel_name in self.config['channels']:
            if not self.device.isOutputOn(channel_name['channel']):
                self.device.outputOn(channel_name['channel'])

        self.make_command('measure_voltage', self.measure_voltage)
        self.make_command('measure_current', self.measure_current)

    def main(self):
        # Start channel monitoring threads
        for channel_name in self.channels.keys():
            thread_current = threading.Thread(target=self.monitor_current_channel, args=(channel_name,))
            thread_current.start()

            self.stream_threads[channel_name] = thread_current

            thread_voltage = threading.Thread(target=self.monitor_voltage_channel, args=(channel_name,))
            thread_voltage.start()

            self.stream_threads[channel_name] = thread_voltage

        while not self.should_shut_down:
            time.sleep(0.01)

        for thread in self.stream_threads.values():
            thread.join()
        self.stream_threads = {}

    def monitor_current_channel(self, channel_name):
        while not self.should_shut_down:
            try:
                # Get an update for this channel
                frame = self.current_streams[channel_name].get_next_frame(10)
                value = frame.data
                if value >= self.max_current:
                    raise ValueError(f'Current command exceeds maximum current of {self.max_current} A')

                # Update the device
                channel_number = self.config[self.channels[channel_name]]['channel']
                with self.lock:
                    self.device.setCurrent(value * 1e3, channel=channel_number)   # Convert to mA

            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def monitor_voltage_channel(self, channel_name):
        while not self.should_shut_down:
            try:
                # Get an update for this channel
                frame = self.voltage_streams[channel_name].get_next_frame(10)
                value = frame.data
                if value >= self.max_volts:
                    raise ValueError(f'Voltage command exceeds maximum voltage of {self.max_volts} V')

                # Update the device
                channel_number = self.config[self.channels[channel_name]]['channel']
                with self.lock:
                    self.device.setVoltage(value, channel=channel_number)

            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def close(self):
        for channel_name in self.config['channels']:
            self.device.setVoltage(0, channel=channel_name['channel'])
            self.device.setCurrent(0, channel=channel_name['channel'])
            self.device.outputOff(channel_name['channel'])

        self.device.setLocal()
        self.device.close()

    def measure_voltage(self, channel_name):
        channel_number = self.config[self.channels[channel_name]]['channel']
        return self.device.measureVoltage(channel=channel_number)

    def measure_current(self, channel_name):
        channel_number = self.config[self.channels[channel_name]]['channel']
        return self.device.measureCurrent(channel=channel_number)


if __name__ == '__main__':
    service = AimTtiPlp()
    service.run()
