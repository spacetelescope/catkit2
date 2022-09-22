import heapq
import time

from ..testbed.service import Service

class Simulator(Service):
    def __init__(self, service_type):
        super().__init__(service_type)

        self.callbacks = []
        self.callback_counter = 0

        self.time = self.make_data_stream('time', 'float64', [1], 20)
        self.time.submit_data(np.zeros(1))

        self.make_command('set_breakpoint', self.set_breakpoint)
        self.make_command('release_breakpoint', self.release_breakpoint)

        self.make_command('start_camera_acquisition', self.start_camera_acquisition)
        self.make_command('end_camera_acquisition', self.end_camera_acquisition)

        self.make_command('actuate_dm', self.actuate_dm)
        self.make_command('move_stage', self.move_stage)
        self.make_command('move_filter', self.move_filter)
        self.make_command('move_flip_mount', self.move_flip_mount)

        self.integrating_cameras = {}
        self.camera_integrated_power = {}

    def main(self):
        last_update_time = time.time()

        while not self.should_shut_down:
            # Get the current images on all cameras.
            camera_images = {}

            for camera_name in self.camera_integrated_power.keys():
                wavefronts = self.model.get_wavefronts(camera_name)
                camera_images[camera_name] = sum(wf.power for wf in wavefronts)

            # Get the next callback. If there isn't one, continue.
            if not self.callbacks:
                time.sleep(0.01)
                continue

            callback = heapq.heappop(self.callbacks)
            callback_time, _, callback_func = callback

            # Make sure we are not progressing time faster than some constant times real time.
            if callback_time - self.time.get()[0] > self.alpha * (time.time() - last_update_time):
                heapq.heappush(self.callbacks, callback)

                time.sleep(0.01)
                continue

            # We can now progress the simulator time. First integrate on the cameras.
            integration_time = callback_time - self.time.get()[0]

            for camera_name in self.camera_integrated_power.keys():
                self.camera_integrated_power[camera_name] += camera_images[camera_name] * integration_time

            # Progress time on the simulator.
            self.time.submit_data(np.array([callback_time], dtype='float'))
            last_update_time = time.time()

            # Call the callback.
            callback_func()

    def add_callback(self, t, callback_func):
        heapq.heappush(self.callbacks, (t, self.callback_counter, callback_func))
        self.callback_counter += 1

    def set_breakpoint(self, at_time):
        raise NotImplementedError

    def release_breakpoint(self, breakpoint_token):
        raise NotImplementedError

    def start_camera_acquisition(self, at_time, camera_name, integration_time, frame_interval):
        def callback():
            self.log.info(f'Start camera acquisition on {camera_name} with {integration_time} and {frame_interval}.')

            was_already_integrating = camera_name in self.integrating_cameras

            self.integrating_cameras[camera_name] = (integration_time, frame_interval)

            # Start integration right away, if the camera was not already integrating.
            if not was_already_integrating:
                self.make_camera_reset_callback(camera_name)()

        self.add_callback(at_time, callback)

    def make_camera_reset_callback(self, camera_name):
        def callback():
            if camera_name not in self.integrating_cameras:
                # Camera has stopped.
                return

            self.log.info(f'Reset camera image on {camera_name}.')

            integration_time, frame_interval = self.integrating_cameras[camera_name]

            # Reset camera image.
            self.camera_integrated_power[camera_name] = 0

            # Schedule callback for readout.
            next_readout_time = self.time.get()[0] + integration_time
            next_readout_callback = self.make_camera_readout_callback(camera_name, integration_time, frame_interval)

            self.add_callback(next_readout_time, next_readout_callback)

        return callback

    def make_camera_readout_callback(self, camera_name, integration_time, frame_interval):
        def callback():
            self.log.info(f'Read out camera image on {camera_name}.')

            # Read out camera image and yield image.
            self.camera_readout(camera_name, self.camera_integrated_power[camera_name])

            # Stop camera integration.
            del self.camera_integrated_power[camera_name]

            if camera_name in self.integrating_cameras:
                # We are still integrating, so schedule reset.
                next_reset_time = self.time.get()[0] - integration_time + frame_interval
                next_reset_callback = self.make_camera_reset_callback(camera_name)

                self.add_callback(next_reset_time, next_reset_callback)

        return callback

    def end_camera_acquisition(self, at_time, camera_name):
        def callback():
            self.log.info(f'End camera acquisition on {camera_name}.')
            if camera_name in self.integrating_cameras:
                del self.integrating_cameras[camera_name]

        self.add_callback(at_time, callback)

    def camera_readout(self, camera_name, power):
        pass

    def actuate_dm(self, at_time, dm_name, new_actuators):
        pass

    def move_stage(self, at_time, stage_name, old_stage_position, new_stage_position):
        pass

    def move_filter(self, at_time, filter_wheel_name, new_filter_position):
        pass

    def move_flip_mount(self, at_time, flip_mount_name, new_flip_mount_position):
        pass
