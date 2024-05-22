from ..testbed.service import Service

import threading
import numpy as np


class StoppedAcquisition:
    '''Context manager for stopping and restarting the acquisition temporarily.
    '''
    def __init__(self, cam):
        self.cam = cam

    def __enter__(self):
        self.was_running = self.cam.is_acquiring.get()[0] > 0

        if self.was_running:
            self.cam.end_acquisition()

            # Wait for the acquisition to actually end.
            while self.cam.is_acquiring.get()[0]:
                self.cam.sleep(0.001)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.was_running:
            self.cam.start_acquisition()


class CameraService(Service):
    NUM_FRAMES_IN_BUFFER = 20
    PIXEL_DTYPE = 'float32'

    def __init__(self, service_type):
        super().__init__(service_type)

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

    def open(self):
        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES_IN_BUFFER)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], self.NUM_FRAMES_IN_BUFFER)

        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES_IN_BUFFER)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))

        offset_x = self.config.get('offset_x', 0)
        offset_y = self.config.get('offset_y', 0)

        self.width = self.config.get('width', self.sensor_width - offset_x)
        self.height = self.config.get('height', self.sensor_height - offset_y)
        self.offset_x = offset_x
        self.offset_y = offset_y

        self.gain = self.config.get('gain', 0)
        self.exposure_time = self.config.get('exposure_time', 1000)

        def make_property_helper(property_name, read_only=False, dtype=None):
            if dtype is None:
                dtype = ''

            def getter():
                return getattr(self, property_name)

            if read_only:
                self.make_property(property_name, getter, type=dtype)
                return

            def setter(value):
                setattr(self, property_name, value)

            self.make_property(property_name, getter, setter, type=dtype)

        make_property_helper('width', dtype='int64')
        make_property_helper('height', dtype='int64')
        make_property_helper('offset_x', dtype='int64')
        make_property_helper('offset_y', dtype='int64')

        make_property_helper('exposure_time', dtype='int64')
        make_property_helper('gain', dtype='int64')

        make_property_helper('sensor_width', read_only=True, dtype='int64')
        make_property_helper('sensor_height', read_only=True, dtype='int64')

        self.make_command('start_acquisition', self._start_acquisition)
        self.make_command('end_acquisition', self._end_acquisition)

        self.temperature_thread = threading.Thread(target=self.monitor_temperature)
        self.temperature_thread.start()

    def main(self):
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def close(self):
        self.temperature_thread.join()

    def acquisition_loop(self):
        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])
        has_correct_parameters &= self.images.dtype == self.PIXEL_DTYPE

        if not has_correct_parameters:
            self.images.update_parameters(self.PIXEL_DTYPE, [self.height, self.width], self.NUM_FRAMES_IN_BUFFER)

        # Start acquisition on the camera.
        self.start_acquisition()

        # Communicate to outside that we started acquisition.
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))

        try:
            # Wait until we are commanded to stop acquisition.
            while self.should_be_acquiring.is_set() and not self.should_shut_down:
                img = self.capture_image()

                self.images.submit_data(img)

        finally:
            # Communicate with the simulator to stop camera acquisition.
            self.testbed.simulator.end_camera_acquisition(camera_name=self.id)
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))

    def _start_acquisition(self):
        self.should_be_acquiring.set()

    def _end_acquisition(self):
        self.should_be_acquiring.clear()

    @property
    def width(self):
        # TODO: ROI transformation here.
        return self.get_roi_width()

    @width.setter
    def width(self, width):
        # TODO: ROI transformation here.
        self.set_roi_width(width)

    @property
    def height(self):
        # TODO: ROI transformation here.
        return self.get_roi_height()

    @height.setter
    def height(self, height):
        # TODO: ROI transformation here.
        self.set_roi_height(height)

    @property
    def offset_x(self):
        # TODO: ROI transformation here.
        return self.get_roi_offset_x()

    @offset_x.setter
    def offset_x(self, offset_x):
        # TODO: ROI transformation here.
        self.set_roi_offset_x(offset_x)

    @property
    def offset_y(self):
        # TODO: ROI transformation here.
        return self.get_roi_offset_y()

    @offset_y.setter
    def offset_y(self, offset_y):
        # TODO: ROI transformation here.
        self.set_roi_offset_y(offset_y)

    @property
    def sensor_width(self):
        # TODO: ROI transformation here.
        return self.get_sensor_width()

    @property
    def sensor_height(self):
        # TODO: ROI transformation here.
        return self.get_sensor_height()

    def start_acquisition(self):
        '''Start acquisition sequence on the camera.
        '''
        raise NotImplementedError()

    def end_acquisition(self):
        '''End acquisition sequence on the camera.
        '''
        raise NotImplementedError()

    def capture_image(self):
        '''Capture an image on the camera and return it.
        '''
        raise NotImplementedError()

    def get_roi_width(self):
        '''Get the width of the ROI on the camera.
        '''
        raise NotImplementedError()

    def set_roi_width(self, width):
        '''Set the width of the ROI on the camera.
        '''
        raise NotImplementedError()

    def get_roi_height(self):
        '''Get the height of the ROI on the camera.
        '''
        raise NotImplementedError()

    def set_roi_height(self, height):
        '''Set the height of the ROI on the camera.
        '''
        raise NotImplementedError()

    def get_roi_offset_x(self):
        '''Get the x-offset of the ROI on the camera.
        '''
        raise NotImplementedError()

    def set_roi_offset_x(self, offset_x):
        '''Set the x-offset of the ROI on the camera.
        '''
        raise NotImplementedError()

    def get_roi_offset_y(self):
        '''Get the y-offset of the ROI on the camera.
        '''
        raise NotImplementedError()

    def set_roi_offset_y(self):
        '''Set the y-offset of the ROI on the camera.
        '''
        raise NotImplementedError()

    def get_sensor_width(self):
        '''Get the width of the camera sensor.
        '''
        raise NotImplementedError()

    def get_sensor_height(self):
        '''Get the height of the camera sensor.
        '''
        raise NotImplementedError()

    def get_exposure_time(self):
        '''Get the exposure time on the camera.
        '''
        raise NotImplementedError()

    def set_exposure_time(self):
        '''Set the exposure time on the camera.
        '''
        raise NotImplementedError()

    def get_gain(self):
        '''Get the gain on the camera.
        '''
        raise NotImplementedError()

    def set_gain(self):
        '''Set the gain on the camera.
        '''
        raise NotImplementedError()

    def get_temperature(self):
        '''Get the temperature on the camera.
        '''
        raise NotImplementedError()
