import sys

import zmq

from ..testbed.service import Service
from ..testbed.testbed_proxy import TestbedProxy
from .simulator_pb2 import *

def numpy_to_proto(arr, out=None):
    '''Convert a Numpy array to a ProtoTensor.

    Parameters
    ----------
    arr : ndarray
        The array to be converted.
    out : ProtoTensor
        The output object. If this is None, a new ProtoTensor will be created.

    Returns
    -------
    ProtoTensor
        The created ProtoTensor (or `out` if that was provided).
    '''
    if out is None:
        out = Tensor()

    out.shape[:] = arr.shape
    out.dtype = str(arr.dtype)
    out.data = arr.tobytes()

    if arr.dtype.byteorder == '<':
        out.byte_order = 'little'
    elif arr.dtype.byteorder == '>':
        out.byte_order = 'big'
    elif arr.dtype.byteorder == '=':
        out.byte_order = sys.byteorder
    else:
        out.byte_order = '|'

    return out

def proto_to_numpy(tensor):
    '''Convert a Tensor into a Numpy array.

    Parameters
    ----------
    tensor : Tensor
        The Tensor to convert.

    Returns
    -------
    ndarray
        The created Numpy array.
    '''
    dtype = np.dtype(tensor.dtype).newbyteorder(tensor.byte_order)

    arr = np.frombuffer(tensor.data, dtype=dtype)
    arr = arr.reshape(tensor.shape)

    return arr

class SimulatorClient:
    def __init__(self, service_name, testbed_port):
        testbed = TestbedProxy(testbed_port)
        self.simulator_port = testbed.simulator.port

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.RCVTIMEO = 100

        self.socket.connect(f'tcp://localhost:{self.simulator_port}')

    def actuate_dm(self, at_time, dm_name, new_actuators):
        request = ActuateDMRequest(
            at_time=at_time,
            dm_name=dm_name,
            new_actuators=numpy_to_proto(new_actuators)
        )

        return self._make_simulator_request('actuate_dm', request)

    def move_stage(self, at_time, stage_name, old_stage_position, new_stage_position):
        request = MoveStageRequest(
            at_time=at_time,
            stage_name=stage_name,
            old_stage_position=old_stage_position,
            new_stage_position=new_stage_position
        )

        return self._make_simulator_request('move_stage', request)

    def move_filter(self, at_time, filter_wheel_name, old_filter_position, new_filter_position):
        request = MoveFilterRequest(
            at_time=at_time,
            filter_wheel_name=filter_wheel_name,
            old_filter_position=old_filter_position,
            new_filter_position=new_filter_position
        )

        return self._make_simulator_request('move_filter', request)

    def move_flip_mount(self, at_time, flip_mount_name, old_flip_mount_position, new_flip_mount_position):
        request = MoveFlipMountRequest(
            at_time=at_time,
            flip_mount_name=flip_mount_name,
            old_flip_mount_position=old_flip_mount_position,
            new_flip_mount_position=new_flip_mount_position
        )

        return self._make_simulator_request('move_flip_mount', request)

    def set_breakpoint(self, at_time):
        request = SetBreakpointRequest(
            at_time=at_time
        )

        return self._make_simulator_request('set_breakpoint', request)

    def release_breakpoint(self, breakpoint_token):
        request = ReleaseBreakpointRequest(
            breakpoint_token=breakpoint_token
        )

        return self._make_simulator_request('release_breakpoint', request)

    def start_camera_acquisition(self, camera_name, start_time, integration_time, frame_interval):
        request = StartCameraAcquisitionRequest(
            camera_name=camera_name,
            start_time=start_time,
            integration_time=integration_time,
            frame_interval=frame_interval
        )

        return self._make_simulator_request('start_camera_acquisition', request)

    def end_camera_acquisition(self, camera_name):
        request = EndCameraAcquisitionRequest(
            camera_name=camera_name
        )

        return self._make_simulator_request('end_camera_acquisition', request)

    def _make_simulator_request(self, func_name, request):
        self.socket.send_multipart([func_name.encode('ascii'), request.SerializeToString()])

        while True:
            try:
                reply = self.socket.recv_multipart()[0]

                # Reply is either "ok " + description or "error " + description.
                reply = reply.decode('ascii')

                if reply.startswith('error '):
                    # Raise an error with the error description.
                    raise RuntimeError(reply[6:])
                else:
                    if len(reply) > 3:
                        return reply[3:]
                    else:
                        return None
            except zmq.ZMQError as e:
                if e.errno == zmq.EAGAIN:
                    # Timed out
                    continue
                else:
                    print('error', e)
                    raise
