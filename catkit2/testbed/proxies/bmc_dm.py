from ..service_proxy import ServiceProxy

import numpy as np
from astropy.io import fits

@ServiceProxy.register_service_interface('bmc_dm')
class BmcDmProxy(ServiceProxy):
    @property
    def dm_mask(self):
        if not hasattr(self, '_dm_mask'):
            fname = self.configuration['dm_mask_fname']

            self._dm_mask = fits.getdata(fname).astype('bool')

        return self._dm_mask

    @property
    def num_actuators(self):
        return self.configuration['num_actuators']

    def dm_shapes_to_command(self, dm1_shape, dm2_shape=None):
        command = np.zeros(2048)

        if dm2_shape is None:
            command[:952] = dm1_shape[:952]
            command[1024:1024 + 952] = dm1_shape[952:]
        else:
            command[:952] = dm1_shape[self.dm_mask]
            command[1024:1024 + 952] = dm2_shape[self.dm_mask]

        return command

    def command_to_dm_shapes(self, command):
        dm1_shape = np.zeros((34, 34))
        dm2_shape = np.zeros((34, 34))

        dm1_shape[self.dm_mask] = command[:952]
        dm2_shape[self.dm_mask] = command[1024:1024 + 952]

        return dm1_shape, dm2_shape

    def apply_shape(self, channel, dm1_shape, dm2_shape=None):
        command = self.dm_shapes_to_command(dm1_shape, dm2_shape)

        getattr(self, channel).submit_data(command)
