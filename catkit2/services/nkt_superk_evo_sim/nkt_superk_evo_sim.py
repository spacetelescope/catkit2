from catkit2.testbed.service import Service

import numpy as np

class NktSuperkEvoSim(Service):
    def __init__(self):
        super().__init__('nkt_superk_evo_sim')

        self._power_setpoint = 100
        self._emission = 1

    def open(self):
        self.base_temperature = self.make_data_stream('base_temperature', 'float32', [1], 20)
        self.supply_voltage = self.make_data_stream('supply_voltage', 'float32', [1], 20)
        self.external_control_input = self.make_data_stream('external_control_input', 'float32', [1], 20)

        self.make_property('power_setpoint', self.get_power_setpoint, self.set_power_setpoint)
        self.make_property('emission', self.get_emission, self.set_emission)

    def main(self):
        while not self.should_shut_down:
            # Submit bogus quantities on datastreams.
            self.base_temperature.submit_data(np.array([28.5], dtype='float32'))
            self.supply_voltage.submit_data(np.array([5.5], dtype='float32'))
            self.external_control_input.submit_data(np.array([0], dtype='float32'))

            self.sleep(1)

    def get_power_setpoint(self):
        return self._power_setpoint

    def set_power_setpoint(self, power_setpoint):
        self._power_setpoint = power_setpoint

        self.update_power()

    def get_emission(self):
        return self._emission

    def set_emission(self, emission):
        self._emission = bool(emission)

        self.update_power()

    def update_power(self):
        power = self._power_setpoint * self._emission * 100

        self.testbed.simulator.set_source(power=power)

if __name__ == '__main__':
    service = NktSuperkEvoSim()
    service.run()
