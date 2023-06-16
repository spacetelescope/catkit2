from catkit2 import Service

import numpy as np

class DummyDmService(Service):
    def __init__(self):
        super().__init__('dummy_dm_service')

        self.num_actuators = 952
        self.channel_names = ['correction_howfs', 'correction_lowfs', 'probe', 'poke', 'aberration', 'atmosphere', 'astrogrid', 'resume', 'flat', 'total']
        for channel in self.channel_names:
            setattr(self, channel, np.zeros(2 * self.num_actuators))

    def open(self):
        self.make_property('num_actuators', self.get_actuators)
        for channel in self.channel_names:
            self.make_property(channel, self.get_channel(channel), self.set_channel(channel))

    def main(self):
        while not self.should_shut_down:
            self.sleep(0.1)

    def get_actuators(self):
        return self.num_actuators

    def get_channel(self, channel):
        def get():
            return getattr(self, channel)

        return get

    def set_channel(self, channel):
        def set(value):
            setattr(self, channel, value)

        return set

    def close(self):
        pass



if __name__ == '__main__':
    service = DummyDmService()
    service.run()
