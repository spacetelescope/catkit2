import zmq

from ..protocol.service import Service
from ..protocol.client import TestbedClient
from .simulator_pb2 import *

class SimulatedService(Service):
    def __init__(self, service_name, service_type, testbed_port):
        super().__init__(service_name, service_type, testbed_port)

        testbed = TestbedClient(testbed_port)
        self.simulator_port = testbed.simulator.port

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.RCVTIMEO = 100

        self.socket.connect(f'tcp://localhost:{self.simulator_port}')

    def start_camera_acquisition(self, camera_name, start_time, integration_time, frame_interval):
        request = StartCameraAcquisitionRequest(
            camera_name=camera_name,
            start_time=start_time,
            integration_time=integration_time,
            frame_interval=frame_interval
        )

        return self._make_simulator_request('start_camera_acquisition', request)

    def _make_simulator_request(self, func_name, request):
        self.socket.send_multipart([func_name.encode('ascii', request.SerializeToString()])

        res = Reply()
        while True:
            try:
                reply = self.socket.recv_multipart()[0]

                res.ParseFromString(reply)
                return res
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    # Timed out
                    continue
                else:
                    print('error', e)
                    raise
