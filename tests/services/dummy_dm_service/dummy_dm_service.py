from catkit2 import Service

import numpy as np


class DummyDmService(Service):
    def __init__(self):
        super().__init__('dummy_dm_service')

        self.channel_names = ['correction_howfs', 'correction_lowfs', 'aberration', 'atmosphere']
        self.num_actuators = self.config['num_actuators']

    def open(self):
        # Make channels streamable
        for channel in self.channel_names:
            setattr(self, channel, self.make_data_stream(channel, 'float64', [self.num_actuators], 20))
            getattr(self, channel).submit_data(np.zeros(self.num_actuators,))

    def main(self):
        while not self.should_shut_down:
            self.sleep(0.1)


if __name__ == '__main__':
    service = DummyDmService()
    service.run()
