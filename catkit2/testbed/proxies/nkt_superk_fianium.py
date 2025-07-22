import numpy as np
import time

from ..service_proxy import ServiceProxy


class NktSuperkFianiumProxy(ServiceProxy):
    @property
    def center_wavelength(self):
        return (self.swp_setpoint.get()[0] + self.lwp_setpoint.get()[0]) / 2

    @center_wavelength.setter
    def center_wavelength(self, center_wavelength):
        self.set_spectrum(center_wavelength=center_wavelength, wait=False)

    @property
    def bandwidth(self):
        return self.swp_setpoint.get()[0] - self.lwp_setpoint.get()[0]

    @bandwidth.setter
    def bandwidth(self, bandwidth):
        self.set_spectrum(bandwidth=bandwidth, wait=False)

    def set_spectrum(self, center_wavelength=None, bandwidth=None, wait=True):
        """Set both center wavelength and bandwidth simultaneously.

        Will update the pulse picker ratio if the bandwidth is increased.

        Parameters
        ----------
        center_wavelength : scalar, optional
            The new center wavelength of the tunable filter. If this is not given, the
            center wavelength will not be changed.
        bandwidth : scalar, optional
            The new bandwidth of the tunable filter. If this is not given, the bandwidth
            will not be changed.
        """
        update_pulse_picker = False

        if center_wavelength is None:
            center_wavelength = self.center_wavelength

        if bandwidth is None:
            bandwidth = self.bandwidth
            # We are not changing the bandwidth, so no need to update pulse picker.
        elif bandwidth > self.bandwidth:
            update_pulse_picker = True
            new_pulse_picker = max(int(bandwidth / self.config['pulse_picker_safety']), 1)
        elif bandwidth < self.bandwidth:
            update_pulse_picker = False  # TODO: What to do if bandwidth is reduced?
            new_pulse_picker = max(int(bandwidth / self.config['pulse_picker_safety']), 1)  # TODO: What to do if bandwidth is reduced?

        # Raise an error if the bandwidth is negative for safety reasons.
        if bandwidth < 0:
            raise ValueError('Negative bandwidths are considered dangerous for the NKT VARIA.')

        lwp = center_wavelength - bandwidth / 2
        swp = center_wavelength + bandwidth / 2

        current_lwp = self.lwp_setpoint.get()[0]
        current_swp = self.swp_setpoint.get()[0]

        # Back out early if we do not need to move the VARIA filter.
        if np.allclose(lwp, current_lwp) and np.allclose(swp, current_swp):
            return

        sleep_time = max(abs(lwp - current_lwp), abs(swp - current_swp)) * self.sleep_time_per_nm

        self.lwp_setpoint.submit_data(np.array([lwp], dtype='float32'))
        self.swp_setpoint.submit_data(np.array([swp], dtype='float32'))

        if wait:
            time.sleep(self.base_sleep_time + sleep_time)

        if update_pulse_picker:
            self.pulse_picker_ratio.submit_data(np.array([new_pulse_picker], dtype='uint16'))

    @property
    def sleep_time_per_nm(self):
        return self.config['sleep_time_per_nm']

    @property
    def base_sleep_time(self):
        return self.config['base_sleep_time']

    def turn_on(self):
        self.testbed.nkt_superk.emission.submit_data(np.array([3], dtype='uint8'))

    def turn_off(self):
        self.testbed.nkt_superk.emission.submit_data(np.array([0], dtype='uint8'))
