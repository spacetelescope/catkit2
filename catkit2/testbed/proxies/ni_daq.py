from ..service_proxy import ServiceProxy


class NiDaqProxy(ServiceProxy):
    def apply_voltage(self, channel, voltage, timeout=None):
        getattr(self, channel).submit_data(voltage)
