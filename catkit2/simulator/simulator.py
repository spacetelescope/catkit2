import heapq

import zmq

from ..testbed.service import Service

class Simulator(Service):
    def __init__(self, service_type):
        super().__init__(service_type)

        self.callbacks = []
        self.callback_counter = 0

        self.time = self.make_data_stream('time', 'float64', [1], 20)

        self.make_command('set_breakpoint', self.set_breakpoint)
        self.make_command('release_breakpoint', self.release_breakpoint)

        self.make_command('start_camera_acquisition', self.start_camera_acquition)
        self.make_command('end_camera_acquisition', self.end_camera_acquisition)

        self.make_command('actuate_dm', self.actuate_dm)
        self.make_command('move_stage', self.move_stage)
        self.make_command('move_filter', self.move_filter)
        self.make_command('move_flip_mount', self.move_flip_mount)

        self.running_cameras = {}

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)  # TODO: step through callbacks and handle them.

    def add_callback(self, t, callback):
        heapq.heappush(self.callbacks, (t, self.callback_counter, callback))
        self.callback_counter += 1

    def set_breakpoint(self, at_time):
        raise NotImplementedError

    def release_breakpoint(self, breakpoint_token):
        raise NotImplementedError

    def start_camera_acquisition(self, camera_name, start_time, integration_time, frame_interval):
        pass

    def end_camera_acquisition(self, camera_name):
        pass

    def actuate_dm(self, at_time, dm_name, new_actuators):
        pass

    def move_stage(self, at_time, stage_name, old_stage_position, new_stage_position):
        pass

    def move_filter(self, at_time, filter_wheel_name, new_filter_position):
        pass

    def move_flip_mount(self, at_time, flip_mount_name, new_flip_mount_position):
        pass
