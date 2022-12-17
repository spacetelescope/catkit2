import numpy as np

from catkit2.testbed.service import Service

class ThorlabsPMSim(Service):
    def __init__(self):
        super().__init__('thorlabs_pm_sim')

        self.interval = self.config.get('interval', 10)

        self.power = self.make_data_stream('power', 'float64', [1], 20)

    def main(self):
        while not self.should_shut_down:
            power = self.get_power()
            self.power.submit_data(np.array([power]))

            self.sleep(self.interval)

    def get_power(self):
        return 1  # Watt

if __name__ == '__main__':
    service = ThorlabsPMSim()
    service.run()
