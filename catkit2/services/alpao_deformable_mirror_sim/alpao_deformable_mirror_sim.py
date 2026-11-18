from catkit2.base_services.alpao_deformable_mirror import AlpaoDeformableMirror
from catkit2.testbed.tracing import trace_interval


class AlpaoDeformableMirrorSim(AlpaoDeformableMirror):
    def __init__(self, service_type='alpao_deformable_mirror_sim'):
        super().__init__(service_type)

    def send_to_device(self):
        with trace_interval('send data'):
            self.testbed.simulator.actuate_dm(dm_name=self.id, new_actuators=self.discretized_surface)


if __name__ == '__main__':
    service = AlpaoDeformableMirrorSim()
    service.run()
