import numpy as np
import time

from ..service_proxy import ServiceProxy


class NktSuperkCompactProxy(ServiceProxy):
    def __setattr__(self, name, value):
        # ServiceProxy.__setattr__ handles data streams before class
        # descriptors. Since the COMPACT service has an ``emission`` data
        # stream, explicitly route assignments to this convenience property.
        if name == 'emission':
            type(self).emission.fset(self, value)
            return

        super().__setattr__(name, value)

    @staticmethod
    def _scalar(value):
        return value.get()[0]

    @staticmethod
    def _submit_scalar(stream, value, dtype):
        stream.submit_data(np.array([value], dtype=dtype))

    @property
    def emission(self):
        '''Whether SuperK COMPACT emission is enabled.'''
        # The COMPACT emission register (0x30) is 0=off / 1=on.
        return bool(self._scalar(self.get_data_stream('emission')))

    @emission.setter
    def emission(self, enabled):
        self._submit_scalar(self.get_data_stream('emission'), int(enabled), 'uint8')

    @property
    def power_level(self):
        '''The requested SuperK COMPACT output power level in percent.'''
        return float(self._scalar(self.power_setpoint))

    @power_level.setter
    def power_level(self, power_level):
        power_level = float(power_level)
        if not 0 <= power_level <= 100:
            raise ValueError('The COMPACT power level must be between 0 and 100 %.')

        self._submit_scalar(self.power_setpoint, power_level, 'float32')

    @property
    def center_wavelength(self):
        return (self._scalar(self.swp_setpoint) + self._scalar(self.lwp_setpoint)) / 2


    @center_wavelength.setter
    def center_wavelength(self, center_wavelength):
        self.set_spectrum(center_wavelength=center_wavelength, wait=False)

    @property
    def bandwidth(self):
        return self._scalar(self.swp_setpoint) - self._scalar(self.lwp_setpoint)


    @bandwidth.setter
    def bandwidth(self, bandwidth):
        self.set_spectrum(bandwidth=bandwidth, wait=False)

    @property
    def wavelength_settings(self):
        '''The VARIA wavelength settings as ``(center_wavelength, bandwidth)`` in nm.'''
        return self.center_wavelength, self.bandwidth

    @wavelength_settings.setter
    def wavelength_settings(self, settings):
        try:
            center_wavelength = settings['center_wavelength']
            bandwidth = settings['bandwidth']
        except (TypeError, KeyError):
            center_wavelength, bandwidth = settings

        self.set_spectrum(center_wavelength=center_wavelength, bandwidth=bandwidth, wait=False)

    @property
    def wavelength_range(self):
        '''The VARIA wavelength limits as ``(lwp_setpoint, swp_setpoint)`` in nm.'''
        return float(self._scalar(self.lwp_setpoint)), float(self._scalar(self.swp_setpoint))

    @wavelength_range.setter
    def wavelength_range(self, wavelength_range):
        lwp, swp = wavelength_range
        self.set_spectrum(center_wavelength=(lwp + swp) / 2, bandwidth=swp - lwp, wait=False)

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

        # Raise an error if the bandwidth is negative for safety reasons.
        if bandwidth < 0:
            raise ValueError('Negative bandwidths are considered dangerous for the NKT VARIA.')

        lwp = center_wavelength - bandwidth / 2
        swp = center_wavelength + bandwidth / 2

        current_lwp = self._scalar(self.lwp_setpoint)
        current_swp = self._scalar(self.swp_setpoint)


        # Back out early if we do not need to move the VARIA filter.
        if np.allclose(lwp, current_lwp) and np.allclose(swp, current_swp):
            return

        sleep_time = max(abs(lwp - current_lwp), abs(swp - current_swp)) * self.sleep_time_per_nm

        self._submit_scalar(self.lwp_setpoint, lwp, 'float32')
        self._submit_scalar(self.swp_setpoint, swp, 'float32')


        if wait:
            time.sleep(self.base_sleep_time + sleep_time)

    @property
    def sleep_time_per_nm(self):
        return self.config['sleep_time_per_nm']

    @property
    def base_sleep_time(self):
        return self.config['base_sleep_time']

    def turn_on(self):
        self.emission = True

    def turn_off(self):
        self.emission = False

