import numpy as np
import time

from ..service_proxy import ServiceProxy


class NktSuperkProxy(ServiceProxy):
    @property
    def center_wavelength(self):
        print('Getting central wavelength...')
        return (self.swp_setpoint.get()[0] + self.lwp_setpoint.get()[0]) / 2

    @center_wavelength.setter
    def center_wavelength(self, center_wavelength):
        print('Setting central wavelength...')
        self.set_spectrum(center_wavelength=center_wavelength, wait=False)

    @property
    def bandwidth(self):
        print('Getting bandwidth value...')
        return self.swp_setpoint.get()[0] - self.lwp_setpoint.get()[0]

    @bandwidth.setter
    def bandwidth(self, bandwidth):
        print('Setting bandwidth value...')
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

    @property
    def sleep_time_per_nm(self):
        return self.config['sleep_time_per_nm']

    @property
    def base_sleep_time(self):
        return self.config['base_sleep_time']
    
    @property
    def emission(self):
        return self.emission.get()[0]
    
    def turn_on(self):
        emission = self.emission
        if emission is False:
            self.emission.submit_data(np.array([1], dtype='uint8'))
            print('NKT turned ON')
        else:
            print('NKT already ON')

    def turn_off(self):
        emission = self.emission
        if emission is True:
            self.emission.submit_data(np.array([0], dtype='uint8'))
            print('NKT turned OFF')
        else:
            print('NKT already OFF')

    
    @property
    def power(self):
        print('Getting power value...')
        return self.power_setpoint.get()[0]

    @power.setter
    def power(self, power):
        print('Setting power value...')
        self.power_setpoint.submit_data(np.array([power], dtype='float32'))


    @property
    def pulse_picker_ratio(self):
        print('Getting pulse_picker_ratio value...')
        try:
            return self.pulse_picker_ratio.get()[0]
        except RuntimeError:
                # The frame wasn't available anymore because we were waiting too long.
                print('Could not getting pulse picker ratio')
        
    @pulse_picker_ratio.setter
    def pulse_picker_ratio(self, pulse_picker_ratio):
        print('Setting pulse_picker_ratio value...')
        try:
            self.pulse_picker_ratio.submit_data(np.array([pulse_picker_ratio], dtype='float32'))
        except RuntimeError:
                # The frame wasn't available anymore because we were waiting too long.
                print('Could not setting pulse picker ratio')


