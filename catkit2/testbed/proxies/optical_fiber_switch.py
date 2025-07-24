from catkit2.testbed import ServiceProxy
import numpy as np
import time


class OpticalFiberSwitchProxy(ServiceProxy):
    wait_time = 0.1

    def set_channel(self, channel, wait=True):
        channel = self.resolve_channel(channel)
        self.input_channel.submit_data(np.array([channel], dtype='int8'))

        if wait:
            time.sleep(self.wait_time)

    def resolve_channel(self, channel):
        if isinstance(channel, str):
            # The channel is a named channel.
            channel = self.channels[channel]

            # The channel may still be a named channel, so try to resolve deeper.
            return self.resolve_channel(channel)
        else:
            return channel

    @property
    def channels(self):
        return self.config['channels']

