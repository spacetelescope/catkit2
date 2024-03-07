from ..service_proxy import ServiceProxy


@ServiceProxy.register_service_interface('ni_daq')
class NiDaqProxy(ServiceProxy):
    def apply_voltage(self, channel, voltage, timeout=None):
        getattr(self, channel).submit_data(voltage)
