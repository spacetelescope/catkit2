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
