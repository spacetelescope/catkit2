from catkit2.base_services.bmc_deformable_mirror import BmcDeformableMirror
from catkit2.testbed.tracing import trace_interval
import threading


class BmcDeformableMirrorSim(BmcDeformableMirror):
    def __init__(self, service_type='bmc_deformable_mirror_sim'):
        super().__init__(service_type)

        self.lock = threading.Lock()

    def send_to_device(self):
        with trace_interval('send data'):
            with self.lock:
                self.testbed.simulator.actuate_dm(dm_name=self.id, new_actuators=self.discretized_surface)


if __name__ == '__main__':
    service = BmcDeformableMirrorSim()
    service.run()
