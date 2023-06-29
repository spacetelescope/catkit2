import numpy as np
import time

from ..service_proxy import ServiceProxy

@ServiceProxy.register_service_interface('nkt_superk')
class NktSuperkProxy(ServiceProxy):
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
        '''Set both center wavelength and bandwidth simultaneously.

        Parameters
        ----------
        center_wavelength : scalar, optional
            The new center wavelength of the tunable filter. If this is not given, the
            center wavelength will not be changed.
        bandwidth : scalar, optional
            The new bandwidth of the tunable filter. If this is not given, the bandwidth
            will not be changed.
        '''
        if center_wavelength is None:
            center_wavelength = self.center_wavelength

        if bandwidth is None:
            bandwidth = self.bandwidth

        # Ensure the bandwidth is positive for safety reasons.
        if bandwidth < 2:
            bandwidth = 2
            raise ValueError('Negative bandwidths are not allowed.')

        lwp = center_wavelength - bandwidth / 2
        swp = center_wavelength + bandwidth / 2

        current_lwp = self.lwp_setpoint.get()[0]
        current_swp = self.lwp_setpoint.get()[0]

        sleep_time = max(abs(lwp - current_lwp), abs(swp - current_swp)) * self.sleep_time_per_nm

        self.lwp_setpoint.submit_data(np.array([lwp], dtype='float32'))
        self.swp_setpoint.submit_data(np.array([swp], dtype='float32'))

        if wait:
            time.sleep(self.base_sleep_time + sleep_time)

    @property
    def sleep_time_per_nm(self):
        return self.config['sleep_time_per_nm']

    @property
    def base_sleep_time(self):
        return self.config['base_sleep_time']
