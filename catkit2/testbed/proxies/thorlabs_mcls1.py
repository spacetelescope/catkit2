from ..service_proxy import ServiceProxy

@ServiceProxy.register_service_interface('thorlabs_mcls1')
class ThorlabsMCLS1(ServiceProxy):
    @property
    def center_wavelength(self):
        pass

    @property
    def bandwidth(self):
        pass