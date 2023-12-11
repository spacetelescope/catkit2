from catkit2.testbed.service import Service

from dcps import AimTTiPPL


class AimTtiPlp(Service):
    def __init__(self):
        super().__init__('aim_tti_plp')

        self.visa_id = self.config['visa_id']
        self.max_volts = self.config['max_volts']
        self.max_current = self.config['max_current']

        self.lock = threading.Lock()

        self.streams = {}
        self.stream_names = ['voltage', 'current']
        self.stream_threads = {}
        for channel_name in self.config['channels']:
            self.add_channel(channel_name)

    def add_channel(self, channel_name):
        for name in self.stream_names:
            stream = channel_name.lower() + '_' + name
            self.streams[stream] = self.make_data_stream(stream, 'float32', [1], 20)

    def open(self):
        self.device = AimTTiPPL(self.visa_id)
        self.device.open()

        for channel_name in self.config['channels']:
            if not self.device.isOutputOn(channel_name['channel']):
                self.device.outputOn(channel_name['channel'])

    def main(self):
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
                # Get an update for this channel
                self.channels[channel_name].get_next_frame(10)

                # TODO: differentiate between voltage and current, then apply respective command
                # TODO: add check for max voltage and current - could put that in separate method
                self.device.setVoltage(voltage, channel=self.config[self.channels[channel_name]]['channel'])
                self.device.setCurrent(current, channel=self.config[self.channels[channel_name]]['channel'])

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


if __name__ == '__main__':
    service = AimTtiPlp()
    service.run()
