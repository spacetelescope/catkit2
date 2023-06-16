from catkit2 import Service

import numpy as np

class DummyDmService(Service):
    def __init__(self):
        super().__init__('dummy_dm_service')

        #self.num_actuators = 952
        #self.channel_names = ['correction_howfs', 'correction_lowfs', 'probe', 'poke', 'aberration', 'atmosphere', 'astrogrid', 'resume', 'flat', 'total']
        #for channel in self.channel_names:
        #    setattr(self, channel, np.zeros(2 * self.num_actuators))

    def main(self):
        while not self.should_shut_down:
            self.sleep(0.1)

    def close(self):
        pass



if __name__ == '__main__':
    service = DummyDmService()
    service.run()
