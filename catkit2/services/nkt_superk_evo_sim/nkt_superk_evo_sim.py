from catkit2.base_services.nkt_superk import NktSuperk

import numpy as np


class NktSuperkEvoSim(NktSuperk):
    """The simulated service for both the NKT SuperK EVO and NKT SuperK VARIA."""
    def __init__(self):
        super().__init__('nkt_superk_evo_sim')

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
