import time

import numpy as np

from ..service_proxy import ServiceProxy

# Empirical startup allowance (see issue #472): light appears about 6.1 s after emission is enabled,
# and changing power during startup can leave the source without output. The blocking wait only
# protects sequential callers; it does not stop another client from changing power concurrently.
STARTUP_TIME = 6.5


class ThorlabsS4fcProxy(ServiceProxy):
    @property
    def center_wavelength(self):
        return self.config['center_wavelength']

    @property
    def bandwidth(self):
        return self.config['bandwidth']

    def turn_on(self):
        """Enable emission and wait for the source to start up.

        The emission datastream reflects the requested state, not measured optical output.
        """
        self.emission.submit_data(np.array([1], dtype='uint8'))
        time.sleep(STARTUP_TIME)

    def turn_off(self):
        """Disable emission."""
        self.emission.submit_data(np.array([0], dtype='uint8'))
