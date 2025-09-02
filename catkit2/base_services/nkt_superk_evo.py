from catkit2.base_services.nkt_superk import NktSuperk

import numpy as np


class NktSuperkEvo(NktSuperk):
    '''The base service for both the NKT SuperK EVO and NKT SuperK VARIA.

    Both devices are combined into a single service due to the need for
    a single open port to the device that cannot be shared between
    multiple services.
    '''
    def __init__(self, service_type):
        super().__init__(service_type)

    def _create_device_specific_streams(self):
        """Create EVO-specific data streams."""
        # EVO-specific streams
        self.base_temperature = self.make_data_stream('base_temperature', 'float32', [1], 20)
        self.supply_voltage = self.make_data_stream('supply_voltage', 'float32', [1], 20)
        self.external_control_input = self.make_data_stream('external_control_input', 'float32', [1], 20)
        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)

        # Set initial EVO setpoints from config
        self.current_setpoint.submit_data(np.array([self.config['current_setpoint']], dtype='float32'))

    def _get_device_specific_funcs(self):
        """Get EVO-specific thread functions."""
        return {
            'power_setpoint': self.monitor_func(self.power_setpoint, self.set_power_setpoint),
            'current_setpoint': self.monitor_func(self.current_setpoint, self.set_current_setpoint),
            'evo_status': self.update_func(self.update_evo_status)
        }

    def _device_specific_cleanup(self):
        """Perform EVO-specific cleanup."""
        # No specific cleanup needed for EVO
        pass
