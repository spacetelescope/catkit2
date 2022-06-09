from ..service_proxy import ServiceProxy

import numpy as np
import time

@ServiceProxy.register_service_interface('web_power_switch')
class WebPowerSwitchProxy(ServiceProxy):
    def switch(self, outlet_name, on):
        if outlet_name.lower() not in self.outlets:
            raise ValueError(f'\"{outlet_name}\" is not one of the outlets.')

        channel = getattr(self, outlet_name.lower())
        channel.submit_data(np.ones(1, dtype='int8') * on)

    def turn_on(self, outlet_name):
        self.switch(outlet_name, True)

    def turn_off(self, outlet_name):
        self.switch(outlet_name, False)

    @property
    def outlets(self):
        return [key.lower() for key in self.configuration['outlets'].keys()]
