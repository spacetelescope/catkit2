from ..service_proxy import ServiceProxy


class ThorlabsS4fcProxy(ServiceProxy):
    @property
    def center_wavelength(self):
        return self.config['center_wavelength']

    @property
    def bandwidth(self):
        return self.config['bandwidth']
