from catkit2.base_services.nkt_superk import NktSuperk

import numpy as np


class NktSuperkEvoSim(NktSuperk):
    def __init__(self):
        super().__init__('nkt_superk_evo_sim')

    def _create_device_specific_streams(self):
        """Create EVO-specific data streams."""
        # EVO-specific streams
        self.base_temperature = self.make_data_stream('base_temperature', 'float32', [1], 20)
        self.supply_voltage = self.make_data_stream('supply_voltage', 'float32', [1], 20)
        self.external_control_input = self.make_data_stream('external_control_input', 'float32', [1], 20)

        self.power_setpoint = self.make_data_stream('power_setpoint', 'float32', [1], 20)
        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)

        # Set initial EVO setpoints from config
        self.power_setpoint.submit_data(np.array([self.config['power_setpoint']], dtype='float32'))
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
        pass

    def update_evo_status(self):
        """Update EVO-specific status information."""
        self.base_temperature.submit_data(np.array([28.5], dtype='float32'))
        self.supply_voltage.submit_data(np.array([24.1], dtype='float32'))
        self.external_control_input.submit_data(np.array([4.2], dtype='float32'))

    def set_emission(self, emission):
        """Set emission state for EVO device in simulator."""
        self.testbed.simulator.set_source_power(
            source_name=self.id,
            power=emission * self.power_setpoint.get()[0] * 1e-2
        )

    def set_power_setpoint(self, power_setpoint):
        """Set power setpoint for EVO device in simulator."""
        self.testbed.simulator.set_source_power(
            source_name=self.id,
            power=self.emission.get()[0] * power_setpoint * 1e-2
        )

    def set_current_setpoint(self, current_setpoint):
        """Set current setpoint for EVO device (no-op in simulation)."""
        pass


if __name__ == '__main__':
    service = NktSuperkEvoSim()
    service.run()
