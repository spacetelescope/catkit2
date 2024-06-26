import numpy as np
import time

from catkit2.testbed.service import Service

class ThorlabsTSP01Sim(Service):
    def __init__(self):
        super().__init__('thorlabs_tsp01_sim')

        self.interval = self.config.get('interval', 10)

        self.temperature_internal = self.make_data_stream('temperature_internal', 'float64', [1], 20)
        self.temperature_header_1 = self.make_data_stream('temperature_header_1', 'float64', [1], 20)
        self.temperature_header_2 = self.make_data_stream('temperature_header_2', 'float64', [1], 20)
        self.humidity_internal = self.make_data_stream('humidity_internal', 'float64', [1], 20)

        self.shifts = np.random.uniform(0, 2 * np.pi, size=3)
        self.periods = np.random.uniform(300, 1800, size=3)
        self.amplitudes = np.random.uniform(0.1, 1, size=3)
        self.offsets = np.random.uniform(20, 21, size=3)

    def main(self):
        while not self.should_shut_down:
            t1 = self.get_temperature(1)
            t2 = self.get_temperature(2)
            t3 = self.get_temperature(3)
            h = self.get_humidity()

            self.temperature_internal.submit_data(np.array([t1], dtype='float64'))
            self.temperature_header_1.submit_data(np.array([t2], dtype='float64'))
            self.temperature_header_2.submit_data(np.array([t3], dtype='float64'))
            self.humidity_internal.submit_data(np.array([h], dtype='float64'))

            self.sleep(self.interval)

    def get_temperature(self, channel):
        period = self.periods[channel - 1]
        shift = self.shifts[channel - 1]
        amplitude = self.amplitudes[channel - 1]
        offset = self.offsets[channel - 1]

        return np.sin(time.time() * 2 * np.pi / period + shift) * amplitude + offset

    def get_humidity(self):
        return 20

if __name__ == '__main__':
    service = ThorlabsTSP01Sim()
    service.run()
