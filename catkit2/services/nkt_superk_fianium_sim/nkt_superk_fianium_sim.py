from catkit2.base_services.nkt_superk import NktSuperk


class NktSuperkFianiumSim(NktSuperk):
    """The simulated service for both the NKT SuperK FIANIUM and NKT SuperK VARIA."""
    def __init__(self):
        super().__init__('nkt_superk_fianium_sim')

    def set_emission(self, emission):
        """Set emission state for FIANIUM device in simulator."""
        onoff = 0 if emission == 0 else 1
        self.testbed.simulator.set_source_power(
            source_name=self.id,
            power=onoff * self.power_setpoint.get()[0] * 1e-2 * self.pulse_picker_ratio.get()[0]  # TODO: add model conversion for pulse picker ratio
        )

    def set_power_setpoint(self, power_setpoint):
        """Set power setpoint for FIANIUM device in simulator."""
        onoff = 0 if self.emission.get()[0] == 0 else 1
        self.testbed.simulator.set_source_power(
            source_name=self.id,
            power=onoff * power_setpoint * 1e-2 * self.pulse_picker_ratio.get()[0]  # TODO: add model conversion for pulse picker ratio
        )

    def set_pulse_picker_ratio(self, pulse_picker_ratio):
        """Set pulse picker ratio for FIANIUM device in simulator."""
        onoff = 0 if self.emission.get()[0] == 0 else 1
        self.testbed.simulator.set_source_power(
            source_name=self.id,
            power=onoff * self.power_setpoint.get()[0] * 1e-2 * pulse_picker_ratio  # TODO: add model conversion for pulse picker ratio
        )


if __name__ == '__main__':
    service = NktSuperkFianiumSim()
    service.run()
