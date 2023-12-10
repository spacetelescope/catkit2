from catkit2.testbed.service import Service

from dcps import AimTTiPPL
import pyvisa


class AimTtiPlp(Service):
    def __init__(self):
        super().__init__('aim_tti_plp')

        self.visa_id = self.config['visa_id']
        self.channel = self.config['channel']

        self.current = self.make_data_stream(f'current', 'float32', [1], 20)
        self.voltage = self.make_data_stream(f'voltage', 'float32', [1], 20)

    def open(self):
        self.device = AimTTiPPL(self.visa_id)
        self.device.open()

        if not self.device.isOutputOn(self.channel):
            self.device.outputOn(self.channel)

    def main(self):
        while not self.should_shut_down:
            try:
                # Get an update for this channel
                voltage = self.voltage.get_next_frame(10).data[0]
                current = self.current.get_next_frame(10).data[0]

                self.device.setVoltage(voltage, channel=self.channel)
                self.device.setCurrent(current, channel=self.channel)

            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def close(self):
        self.device.outputOff(self.channel)
        self.device.setLocal()
        self.device.close()


if __name__ == '__main__':
    service = AimTtiPlp()
    service.run()
