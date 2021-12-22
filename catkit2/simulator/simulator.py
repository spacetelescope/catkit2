import heapq

import zmq

from .simulator_pb2 import *
from ..testbed.service import Service

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
        super().__init__(service_name, service_type, testbed_port)

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
                msgs = self.socket.recv_multipart()
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
            self.socket.send_multipart([identity, ('error ' + desc).encode('ascii')])

        try:
            res = func(proto)
        except Exception as e:
            desc = f"Command '{cmd}' return an error: '{repr(e)}'."
            self.socket.send_multipart([identity, ('error ' + desc).encode('ascii')])

        response = 'ok '

        if res is not None:
            response += str(res)

        self.socket.send_multipart([identity, response.encode('ascii')])

    def add_callback(self, t, callback):
        heapq.heappush(self.callbacks, (t, self.callback_counter, callback))
        self.callback_counter += 1

    @simulator_request_handler(ActuateDMRequest)
    def on_actuate_dm(self, request):
        pass

    @simulator_request_handler(MoveStageRequest)
    def on_move_stage(self, request):
        pass

    @simulator_request_handler(MoveFilterRequest)
    def on_move_filter(self, request):
        pass

    @simulator_request_handler(MoveFlipMountRequest)
    def on_move_flip_mount(self, request):
        pass

    @simulator_request_handler(SetBreakpointRequest)
    def on_set_breakpoint(self, request):
        raise NotImplementedError

    @simulator_request_handler(ReleaseBreakpointRequest)
    def on_release_breakpoint(self, request):
        raise NotImplementedError

    @simulator_request_handler(StartCameraAcquisitionRequest)
    def on_start_camera_acquisition(self, request):
        pass

    @simulator_request_handler(StopCameraAcquisitionRequest)
    def on_end_camera_acquisition(self, request):
        pass
