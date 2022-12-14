import heapq
import time
import threading
from collections import namedtuple

import numpy as np

from ..testbed.service import Service

class Callback(namedtuple('Callback', ['time', 'id', 'func'])):
    def __eq__(self, b):
        return self.time == b.time and self.id == b.id

class Simulator(Service):
    def __init__(self, service_type, model, max_time_factor=1):
        '''Base class for simultator services.

        This simulator uses a callback system to schedule events on a simulated
        timeline. Methods to be implemented by the derived class integrate with
        a system of simulated services to automate DM actuations, stage movements,
        flip mounts, filter wheels, power strips, and, of course, camera acquisitions.
        Cameras use a reset (which indicates the start of an exposure) and a readout
        (which indicates the end of an exposure). Camera images are integrated over
        time while the other events are handled.

        Parameters
        ----------
        service_type : string
            The service type of the simulator. This will be passed onto the Service
            init().
        model : OpticalModel
            The optical model that the simulator will base its camera images on.
        max_time_factor : scalar
            The maximum speed of the simulated time relative to wall clock time. If
            images are generated too fast, the simulator will slow down to this fraction
            of wall clock time. This enables other services to respond in time and react
            to camera images in the same way as they would do when ran on hardware.
            Default value: 1.

        Attributes
        ----------
        model : OpticalModel
            The optical model that the simulator is basing its images on.
        time : DataStream
            The current simulator time.
        '''
        super().__init__(service_type)

        self.model = model
        self.max_time_factor = max_time_factor

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
        self.make_command('switch_power', self.switch_power)

        self.integrating_cameras = {}
        self.camera_integrated_power = {}
        self.camera_callbacks = {}

        self.lock = threading.Lock()

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
                self.sleep(0.01)
                continue

            with self.lock:
                callback = heapq.heappop(self.callbacks)

            # Make sure we are not progressing time faster than some constant times real time.
            if callback.time - self.time.get()[0] > self.max_time_factor * (time.time() - last_update_time):
                with self.lock:
                    heapq.heappush(self.callbacks, callback)

                self.sleep(0.01)
                continue

            # We can now progress the simulator time. First integrate on the cameras.
            integration_time = callback.time - self.time.get()[0]

            for camera_name in self.camera_integrated_power.keys():
                self.camera_integrated_power[camera_name] += camera_images[camera_name] * integration_time

            # Progress time on the simulator.
            self.time.submit_data(np.array([callback.time], dtype='float'))
            last_update_time = time.time()

            # Call the callback.
            callback.func(callback.time)

    def add_callback(self, callback_func, t=None):
        '''Add a callback to the callback list.

        Parameters
        ----------
        callback_func : function
            The function to execute when the time `t` has been reached by the simulator.
        t : scalar or None
            The simulated time at which to run the function. A value of None (the default)
            indicates that the callback should be executed at the current simulated time.

        Returns
        -------
        Callback
            The created callback.
        '''
        with self.lock:
            if t is None:
                t = self.time.get()[0]

            callback = Callback(time=t, id=self.callback_counter, func=callback_func)
            heapq.heappush(self.callbacks, callback)

            self.callback_counter += 1

        return callback

    def remove_callback(self, callback):
        '''Remove a callback from the list of callbacks.

        This allows the user to cancel a previously added callback. If the
        callback has already been executed, this function is a no-op.

        Parameters
        ----------
        callback : Callback
            The callback which to remove from the list of callbacks.
        '''
        with self.lock:
            if callback not in self.callbacks:
                return

            index = self.callbacks.index(callback)
            self.callbacks[index] = self.callbacks[-1]
            self.callbacks.pop()

            heapq.heapify(self.callbacks)

    def set_breakpoint(self, t_until=None):
        '''Set a breakpoint for the simulator.

        The simulator will pause at this breakpoint until it is released. Currently,
        this functionality is not implemented.

        Parameters
        ----------
        t_until : scalar
            The simulated time of the breakpoint.

        Returns
        -------
        int
            A token for the breakpoint.
        '''
        raise NotImplementedError()

    def release_breakpoint(self, breakpoint_token):
        '''Release a previously set breakpoint.

        This will let the simulator continue past the breakpoint. When the
        breakpoint has not been reached yet, this will have no influence.

        Parameters
        ----------
        breakpoint_token : int
            A token given out by `set_breakpoint()`.
        '''
        raise NotImplementedError()

    def start_camera_acquisition(self, camera_name, integration_time, frame_interval):
        '''Start acquisition on a camera.

        The camera will take images every `frame_interval` seconds with an integration time
        of `integration_time`.

        Parameters
        ----------
        camera_name : string
            The name of the camera.
        integration_time : scalar
            The integration time of the camera.
        frame_interval : scalar
            The time interval between neighboring frames.
        '''
        def callback(t):
            self.log.info(f'Start camera acquisition on {camera_name} with {integration_time} and {frame_interval}.')

            if camera_name in self.camera_callbacks:
                self.remove_callback(self.camera_callbacks[camera_name])

                del self.camera_callbacks[camera_name]

            was_already_integrating = camera_name in self.integrating_cameras

            self.integrating_cameras[camera_name] = (integration_time, frame_interval)

            # Start integration right away, if the camera was not already integrating.
            if not was_already_integrating:
                callback = self.add_callback(self.make_camera_reset_callback(camera_name))

                self.camera_callbacks[camera_name] = callback

        self.add_callback(callback)

    def make_camera_reset_callback(self, camera_name):
        '''Schedule a new reset callback for a camera.

        This function will usually be called a certain time after a camera has been read out.
        This marks the start of an exposure for this camera.

        Parameters
        ----------
        camera_name : string
            The name of the camera.
        '''
        def callback(t):
            if camera_name not in self.integrating_cameras:
                # Camera has stopped.
                return

            self.log.info(f'Reset camera image on {camera_name}.')

            integration_time, frame_interval = self.integrating_cameras[camera_name]

            # Reset camera image.
            self.camera_integrated_power[camera_name] = 0

            # Schedule callback for readout.
            next_readout_time = t + integration_time
            next_readout_callback = self.make_camera_readout_callback(camera_name, integration_time, frame_interval)

            callback = self.add_callback(next_readout_callback, next_readout_time)

            self.camera_callbacks[camera_name] = callback

        return callback

    def make_camera_readout_callback(self, camera_name, integration_time, frame_interval):
        '''Schedule a new readout callback for a camera.

        This function will usually be called a certain time after a camera has been reset.
        This marks the end of an exposure for this camera.

        Parameters
        ----------
        camera_name : string
            The name of the camera.
        integration_time : scalar
            The integration time for this camera.
        frame_interval : scalar
            The time interval between neighboring frames.
        '''
        def callback(t):
            if camera_name not in self.camera_integrated_power:
                return

            self.log.info(f'Read out camera image on {camera_name}.')

            # Read out camera image and yield image.
            self.camera_readout(camera_name, self.camera_integrated_power[camera_name])

            # Stop camera integration.
            del self.camera_integrated_power[camera_name]

            if camera_name in self.integrating_cameras:
                # We are still integrating, so schedule reset.
                next_reset_time = t - integration_time + frame_interval
                next_reset_callback = self.make_camera_reset_callback(camera_name)

                callback = self.add_callback(next_reset_callback, next_reset_time)

                self.camera_callbacks[camera_name] = callback

        return callback

    def end_camera_acquisition(self, camera_name):
        '''End the acquisition loop on a camera.

        The current exposure will be finished, but afterwards, no more exposures
        will be performed on this camera (until the acquisition is started again).

        Parameters
        ----------
        camera_name : string
            The name of the camera.
        '''
        def callback(t):
            self.log.info(f'End camera acquisition on {camera_name}.')
            if camera_name in self.integrating_cameras:
                del self.integrating_cameras[camera_name]

        self.add_callback(callback)

    def camera_readout(self, camera_name, integrated_power):
        '''Read out a camera.

        This function should be overriden by the child class. It is responsible
        for handling the image and submitting it to the right service.

        Parameters
        ----------
        camera_name : string
            The name of the camera.
        integrated_power : hcipy.Field
            The integrated power for this camera, ie. integration time times average
            incident power on each pixel.
        '''
        pass

    def actuate_dm(self, dm_name, new_actuators):
        '''Actuate a DM.

        This function should be overriden by the child class. It is responsible
        for setting the actuators on the DM in its model.

        Parameters
        ----------
        dm_name : string
            The name of the DM.
        new_actuators : ndarray
            The new actuators for this DM.
        '''
        pass

    def move_stage(self, stage_name, old_stage_position, new_stage_position):
        '''Move a stage.

        This function should be overriden by the child class. It is responsible
        for setting the stage position in its model.

        Having access to both the old and new stage position allows for the child
        class to implement movements of a stage over simulated time.

        Parameters
        ----------
        stage_name : string
            The name of the stage.
        old_stage_position : scalar
            The current position of this stage axis.
        new_stage_position : scalar
            The commanded position of this stage axis.
        '''
        pass

    def move_filter(self, filter_wheel_name, new_filter_position):
        '''Move a filter.

        This function should be overriden by the child class. It is responsible
        for setting the filter in its model.

        Parameters
        ----------
        filter_wheel_name : string
            The name of the filter wheel.
        new_filter_position : scalar or child-class defined
            The new filter position for this filter wheel.
        '''
        pass

    def move_flip_mount(self, flip_mount_name, new_flip_mount_position):
        '''Move a flip mount.

        This function should be overriden by the child class. It is responsible
        for setting the flip mount in its model.

        Parameters
        ----------
        flip_mount_name : string
            The name of the flip mount.
        new_flip_mount_position : scalar
            The new position of this flip mount.
        '''
        pass

    def switch_power(self, outlet_name, powered):
        '''Switch power on an outlet on or off.

        This function should be overriden by the child class. It is responsible
        for setting whatever effect this outlet has on the model.

        Parameters
        ----------
        outlet_name : string
            The name of the outlet.
        powered : boolean
            Whether to turn the power on (True) or off (False).
        '''
        pass
