import grpc
from concurrent import futures

import zmq
from .simulator_pb2 import *

def simulator_request_handler(request_class):
    def decorator(func):
        def new_func(self, proto):
            request = request_class()
            request.ParseFromString(proto)

            return func(self, request)
        return new_func
    return decorator

class Simulator(Service):
    def __init__(self, service_name, service_type, testbed_port):
        Service.__init__(service_name, service_type, testbed_port)

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.RCVTIMEO = 100

        self.simulator_port = self.socket.bind_to_random_port('tcp://*')
        self.make_property('port', lambda: self.simulator_port)

        self.callbacks = []
        self.callback_counter = 0

        self.time = self.make_data_stream('time', 'float64', [1], 20)

        self.running_cameras = {}

        self.shutdown_flag = False

    def main(self):
        while not self.shutdown_flag:
            self.handle_messages()

    def shut_down(self):
        self.shutdown_flag = True

    def handle_messages(self):
        # Get message from queue.
        while not self.shutdown_flag:
            try:
                msgs = sim.socket.recv_multipart()
                break
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    # Timed out.
                    continue
                else:
                    print('error', e)
                    raise

        if self.shutdown_flag:
            return

        identity, cmd, proto = msgs
        cmd = cmd.decode('ascii')

        try:
            func = getattr(self, 'on_' + cmd)
        except AttributeError:
            desc = f"Command '{cmd}' is not implemented on this simulator."
            sim.socket.send_multipart([identity, desc.encode('ascii')])

        try:
            func(proto)
        except Exception as e:
            desc = f"Command '{cmd}' return an error: '{repr(e)}'."
            sim.socket.send_multipart([identity, desc.encode('ascii')])

        sim.socket.send_multipart([identity, 'ok'.encode('ascii')])

    def add_callback(self, t, callback):
        heapq.heappush(self.callbacks, (t, self.callback_counter, callback))
        self.callback_counter += 1

    @simulator_request_handler(StartCameraAcquisitionRequest)
    def on_start_camera_acquisition(self, request):
        def start_integration(self, )
        self.add_callback()

    @simulator_request_handler(EndCameraAcquisitionRequest)
    def on_end_camera_acquisition(self, request):
        pass

    @simulator_request_handler(ActuateBostonRequest)
    def on_actuate_boston(self, request):
        def callback(self):
            self.model.dm1.actuators = request.new_actuators[:952]
            self.model.dm2.actuators = request.new_actuators[952:]

            self.model.purge_plane('post_boston_dms')

        self.add_callback(request.at_time, callback)
