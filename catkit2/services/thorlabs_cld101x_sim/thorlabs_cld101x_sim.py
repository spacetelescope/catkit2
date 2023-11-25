from catkit2.testbed.service import Service

import numpy as np


class ThorlabsCLD101XSim(Service):
    def __init__(self):
        super().__init__('thorlabs_cld101x_sim')

        self.wavelength = self.config['wavelength']

        self.current_setpoint = self.make_data_stream(f'current_setpoint_{self.wavelength}', 'float32', [1], 20)
        self.current_percent = self.make_data_stream(f'current_percent_{self.wavelength}', 'float32', [1], 20)

    def open(self):
        self.make_command('set_current_setpoint', self.set_current_setpoint)
        self.max_current = 25  # in Ampere  # TODO: Get this from config?

    def main(self):
        while not self.should_shut_down:
            try:
                # Get an update for this channel
                frame = self.current_percent.get_next_frame(10)
                # Apply new power
                self.set_current_setpoint(frame.data)

            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def close(self):
        pass

    def set_current_setpoint(self, current_percent):
        """
        Set the current setpoint of the laser, controlled as percent of its max current setpoint.

        Parameters
        ----------
        current_percent : int
            Limited to range 0-100, in percent of the max current setpoint in Ampere.
        """
        if current_percent < 0 or current_percent > 100:
            raise ValueError("Current_percent must be between 0 and 100.")

        current_setpoint = current_percent / 100 * self.max_current
        self.testbed.simulator.set_source_power(source_name=self.id, power=current_percent)

        self.current_setpoint.submit_data(np.array([current_setpoint]))


if __name__ == '__main__':
    service = ThorlabsCLD101XSim()
    service.run()
