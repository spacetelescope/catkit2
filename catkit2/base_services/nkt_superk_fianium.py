from catkit2.base_services.nkt_superk import NktSuperk

import numpy as np


class NktSuperkFianium(NktSuperk):
    '''The service for both the NKT SuperK FIANIUM and NKT SuperK VARIA.

    Both devices are combined into a single service due to the need for
    a single open port to the device that cannot be shared between
    multiple services.
    '''
    def __init__(self, service_type):
        super().__init__(service_type)
        self.pulse_picker_safety = self.config.get('pulse_picker_safety')

    def _create_device_specific_streams(self):
        """Create FIANIUM-specific data streams."""
        # FIANIUM-specific streams
        self.pulse_picker_ratio = self.make_data_stream('pulse_picker_ratio', 'uint16', [1], 20)

        # Set initial FIANIUM setpoints from config
        self.pulse_picker_ratio.submit_data(np.array([100], dtype='uint16'))  # Setting a safe default value of 100.

    def _get_device_specific_funcs(self):
        """Get FIANIUM-specific thread functions."""
        return {
            'pulse_picker_ratio': self.monitor_pulse_picker_ratio(self.pulse_picker_ratio, self.set_pulse_picker_ratio)
        }

    def _device_specific_cleanup(self):
        """Perform FIANIUM-specific cleanup."""
        self.pulse_picker_ratio.submit_data(np.array([100], dtype='uint16'))

    def monitor_pulse_picker_ratio(self, stream, setter):
        """Monitor pulse picker ratio with safety checks."""
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

