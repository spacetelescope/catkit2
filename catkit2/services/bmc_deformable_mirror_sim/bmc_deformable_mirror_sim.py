from catkit2.base_services.bmc_deformable_mirror import BmcDeformableMirror
import numpy as np


class BmcDeformableMirrorSim(BmcDeformableMirror):
    def __init__(self):
        super().__init__('bmc_deformable_mirror_sim')

        self.flat_map_command = np.zeros(self.num_actuators * self.num_dms)
        self.gain_map_command = np.zeros(self.num_actuators * self.num_dms)
        self.gain_map_inv_command = np.zeros(self.num_actuators * self.num_dms)  # TODO: Why are these initializations not needed in the hardware service?

    def open(self):
        super().open()

        zeros = np.zeros(self.num_actuators * self.num_dms, dtype='float64')
        self.send_surface(zeros)

    def close(self):
        zeros = np.zeros(self.num_actuators * self.num_dms, dtype='float64')
        self.send_surface(zeros)

        super().close()

    def send_surface(self, total_surface):
        super().send_surface(total_surface)

        with self.lock:
            self.testbed.simulator.actuate_dm(dm_name=self.id, new_actuators=self.discretized_surface)


if __name__ == '__main__':
    service = BmcDeformableMirrorSim()
    service.run()
