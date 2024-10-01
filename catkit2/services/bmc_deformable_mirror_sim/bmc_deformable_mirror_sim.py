from catkit2.base_services.bmc_deformable_mirror import BmcDeformableMirror
import numpy as np
import threading


class BmcDeformableMirrorSim(BmcDeformableMirror):
    def __init__(self):
        super().__init__('bmc_deformable_mirror_sim')

        self.flat_map_command = np.zeros(self.num_actuators * self.num_dms)
        self.gain_map_command = np.zeros(self.num_actuators * self.num_dms)
        self.gain_map_inv_command = np.zeros(self.num_actuators * self.num_dms)  # TODO: Why are these initializations not needed in the hardware service?

        self.lock = threading.Lock()

    def send_to_device(self):
        with self.lock:
            self.testbed.simulator.actuate_dm(dm_name=self.id, new_actuators=self.discretized_surface)


if __name__ == '__main__':
    service = BmcDeformableMirrorSim()
    service.run()
