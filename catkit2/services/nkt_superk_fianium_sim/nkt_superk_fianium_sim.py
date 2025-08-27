from catkit2.base_services.nkt_superk import NktSuperk

import numpy as np


class NktSuperkFianiumSim(NktSuperk):
    def __init__(self):
        super().__init__('nkt_superk_fianium_sim')
        self.pulse_picker_safety = self.config.get('pulse_picker_safety')

    def _create_device_specific_streams(self):
        """Create FIANIUM-specific data streams."""
        # FIANIUM-specific streams
        self.power_setpoint = self.make_data_stream('power_setpoint', 'float32', [1], 20)
        self.pulse_picker_ratio = self.make_data_stream('pulse_picker_ratio', 'uint16', [1], 20)

        # Set initial FIANIUM setpoints from config
        self.power_setpoint.submit_data(np.array([self.config['power_setpoint']], dtype='float32'))
        self.pulse_picker_ratio.submit_data(np.array([100], dtype='uint16'))  # Setting a safe default value of 100.

    def _get_device_specific_funcs(self):
        """Get FIANIUM-specific thread functions."""
        return {
            'power_setpoint': self.monitor_func(self.power_setpoint, self.set_power_setpoint),
            'pulse_picker_ratio': self.monitor_pulse_picker_ratio(self.pulse_picker_ratio, self.set_pulse_picker_ratio)
        }

    def _device_specific_cleanup(self):
        """Perform FIANIUM-specific cleanup."""
        self.pulse_picker_ratio.submit_data(np.array([100], dtype='uint16'))

    def monitor_pulse_picker_ratio(self, stream, setter):
        """Create a monitoring function for pulse picker ratio with safety checks."""
        def func():
            while not self.should_shut_down:
                try:
                    frame = stream.get_next_frame(1)
                except Exception:
                    continue

                bandwidth = self.swp_setpoint.get()[0] - self.lwp_setpoint.get()[0]
                if frame.data[0] >= max(int(bandwidth / self.pulse_picker_safety), 1):
                    setter(frame.data[0])
                else:
                    self.log.warning(f'Pulse picker ratio {frame.data[0]} is too low for the current bandwidth {bandwidth}. Not setting it.')

        return func

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
