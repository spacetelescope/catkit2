import numpy as np

from ..service_proxy import ServiceProxy


class ThorlabsMcls1(ServiceProxy):
    @property
    def channel(self):
        return self.config['channel']

    @property
    def center_wavelength(self):
        return self.config['channels'][str(self.channel)]

    @property
    def bandwidth(self):
        return self.config['bandwidth']

    def turn_on(self):
        """Enable emission."""
        self.emission.submit_data(np.array([1], dtype='uint8'))

    def turn_off(self):
        """Disable emission."""
        self.emission.submit_data(np.array([0], dtype='uint8'))
