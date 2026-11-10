import math
import time

import numpy as np

from ..service_proxy import ServiceProxy


class ThorlabsS4fcProxy(ServiceProxy):
    @property
    def center_wavelength(self):
        return self.config['center_wavelength']

    @property
    def bandwidth(self):
        return self.config['bandwidth']

    def turn_on(self, timeout=30, poll_interval=0.1):
        """Enable emission and wait until the hardware reports it enabled.

        The emission datastream is only the requested state. The wait polls the hardware enable
        readback, which is not a measurement of optical power.

        Parameters
        ----------
        timeout : float
            Maximum time to wait, in seconds.
        poll_interval : float
            Time between readbacks, in seconds.

        Raises
        ------
        ValueError
            If timeout or poll_interval is not finite and positive. Emission is not changed.
        TimeoutError
            If the hardware does not report enabled within the timeout.
        """
        if not (math.isfinite(timeout) and timeout > 0 and math.isfinite(poll_interval) and poll_interval > 0):
            raise ValueError('timeout and poll_interval must be finite and positive.')

        self.emission.submit_data(np.array([1], dtype='uint8'))

        start = time.monotonic()
        while not self.get_enable():
            if time.monotonic() - start > timeout:
                raise TimeoutError(f'S4FC did not report enabled within {timeout} s of the ON request.')

            time.sleep(poll_interval)

    def turn_off(self):
        """Disable emission."""
        self.emission.submit_data(np.array([0], dtype='uint8'))
