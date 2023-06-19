from catkit2 import Service

import numpy as np

class DummyDmService(Service):
    def __init__(self):
        super().__init__('dummy_dm_service')

        self.channel_names = ['correction_howfs', 'correction_lowfs', 'probe', 'poke', 'aberration', 'atmosphere', 'astrogrid', 'resume', 'flat', 'total']

        self.num_actuators = self.config['num_actuators']
        self.dm_shape = self.config['dm_shape']
        self.channel_init_value = self.config['channel_init_value']

    def open(self):
        self.make_property('num_actuators', self.get_actuators)

        # Make channels streamable
        for channel in self.channel_names:
            setattr(self, channel, self.make_data_stream(channel, 'float64', [self.dm_shape], 20))
            getattr(self, channel).submit_data(np.ones(self.dm_shape,)*self.channel_init_value)

    def main(self):
        while not self.should_shut_down:
            self.sleep(0.1)

    def get_actuators(self):
        return self.num_actuators

    def close(self):
        pass



if __name__ == '__main__':
    service = DummyDmService()
    service.run()
