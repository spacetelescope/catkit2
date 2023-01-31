import numpy as np

from ..service_proxy import ServiceProxy

@ServiceProxy.register_service_interface('nkt_superk')
class NktSuperkProxy(ServiceProxy):
    @property
    def center_wavelength(self):
        return (self.swp_setpoint.get()[0] + self.lwp_setpoint.get()[0]) / 2

    @center_wavelength.setter
    def center_wavelength(self, center_wavelength):
        self.set_wavelength_and_bandwidth(center_wavelength=center_wavelength)

    @property
    def bandwidth(self):
        return self.swp_setpoint.get()[0] - self.lwp_setpoint.get()[0]

    @bandwidth.setter
    def bandwidth(self, bandwidth):
        self.set_wavelength_and_bandwidth(bandwidth=bandwidth)

    # TODO: decide if we need this function to be public.
    def set_wavelength_and_bandwidth(self, center_wavelength=None, bandwidth=None):
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
        if bandwidth < 0:
            bandwidth = 0

        lwp = center_wavelength - bandwidth / 2
        swp = center_wavelength + bandwidth / 2

        self.lwp_setpoint.submit_data(np.array([lwp]))
        self.swp_setpoint.submit_data(np.array([swp]))
