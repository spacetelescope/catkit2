from catkit2.testbed.service import Service

import time
import numpy as np

class OmegaIthxW3Sim(Service):
    def __init__(self):
        super().__init__('omega_ithx_w3_sim')

        self.time_interval = self.config['time_interval']

        self.temperature = self.make_data_stream('temperature', 'float64', [1], 20)
        self.humidity = self.make_data_stream('humidity', 'float64', [1], 20)

    def main(self):
        while not self.should_shut_down:
            temp, hum = self.get_temperature_and_humidity()

            self.temperature.submit_data(np.array([temp]))
            self.humidity.submit_data(np.array([hum]))

            self.sleep(self.time_interval)

    def get_temperature_and_humidity(self):
        return 25.0, 10.0

if __name__ == '__main__':
    service = OmegaIthxW3Sim()
    service.run()
