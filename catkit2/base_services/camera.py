from ..testbed.service import Service
from catkit2.testbed.tracing import trace_interval

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
            self.cam._end_acquisition()

            # Wait for the acquisition to actually end.
            while self.cam.is_acquiring.get()[0]:
                self.cam.sleep(0.001)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.was_running:
            self.cam._start_acquisition()


class CameraService(Service):
    NUM_FRAMES_IN_BUFFER = 20
    PIXEL_DTYPE = 'float32'

    def __init__(self, service_type):
        super().__init__(service_type)

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

    def open(self):
        # Use the full sensor size here to always allocate enough shared memory.
        self.log.info('Creating data streams using base camera service')

        # frame orientation
        self.rot90 = self.config.get('rot90', False)
        self.flip_x = self.config.get('flip_x', False)
        self.flip_y = self.config.get('flip_y', False)

        self.log.info('Camera orientation: rot90={}, flip_x={}, flip_y={}'.format(self.rot90, self.flip_x, self.flip_y))
        self.log.info('Configured sensor width: {}, height: {}'.format(self.sensor_width, self.sensor_height))

        # All configured values are in user coordinate system, i.e. the values that the user sees instead of camera coordinates.

        # width and height of the ROI, defaults to full sensor size
        self.width = self.config.get('width', self.sensor_width)
        self.height = self.config.get('height', self.sensor_height)
        self.log.info('Configured ROI width: {}, height: {}'.format(self.width, self.height))

        self.offset_x = self.config.get('offset_x', 0)
        self.offset_y = self.config.get('offset_y', 0)

        self.log.info('Configured offsets x: {}, y: {}'.format(self.offset_x, self.offset_y))

        self.gain = self.config.get('gain', 0)
        self.exposure_time = self.config.get('exposure_time', 1000)

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES_IN_BUFFER)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], self.NUM_FRAMES_IN_BUFFER)

        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES_IN_BUFFER)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))

        def make_property_helper(property_name, read_only=False, requires_stopped_acquisition=False, dtype=None):
            if dtype is None:
                dtype = ''

            if read_only:
                self.make_property(property_name, lambda: getattr(self, property_name))
            else:
                if requires_stopped_acquisition:
                    def setter(val):
                        with StoppedAcquisition(self):
                            setattr(self, property_name, val)
                else:
                    def setter(val):
                        setattr(self, property_name, val)

                self.make_property(property_name, lambda: getattr(self, property_name), setter)

        make_property_helper('width', dtype='int64', requires_stopped_acquisition=self.width_requires_stopped_acquisition)
        make_property_helper('height', dtype='int64', requires_stopped_acquisition=self.height_requires_stopped_acquisition)
        make_property_helper('offset_x', dtype='int64', requires_stopped_acquisition=self.offset_x_requires_stopped_acquisition)
        make_property_helper('offset_y', dtype='int64', requires_stopped_acquisition=self.offset_y_requires_stopped_acquisition)

        make_property_helper('exposure_time', dtype='int64', requires_stopped_acquisition=self.exposure_time_requires_stopped_acquisition)
        make_property_helper('gain', dtype='int64', requires_stopped_acquisition=self.gain_requires_stopped_acquisition)

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

    def monitor_temperature(self):
        while not self.should_shut_down:
            temperature = self.get_temperature()
            self.temperature.submit_data(np.array([temperature]))

            self.sleep(1)

    def close(self):
        self.temperature_thread.join()

    def acquisition_loop(self):
        # Make sure the data stream has the right size, and images have right pixel datatype.
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
                transformed_img = self.rot_flip_image(img)
                with trace_interval('processing frame'):
                    self.images.submit_data(transformed_img.astype('float32'))

        finally:
            self.end_acquisition()
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))

    def rot_flip_image(self, img):
        # rotation needs to happen first
        if self.rot90:
            img = np.rot90(img)
        if self.flip_x:
            img = np.flipud(img)
        if self.flip_y:
            img = np.fliplr(img)
        return np.ascontiguousarray(img)

    def _start_acquisition(self):
        self.should_be_acquiring.set()

    def _end_acquisition(self):
        self.should_be_acquiring.clear()

    @property
    def exposure_time(self):
        return self.get_exposure_time()

    @exposure_time.setter
    def exposure_time(self, exposure_time):
        self.set_exposure_time(exposure_time)

    @property
    def width(self):
        if self.rot90:
            return int(self.get_roi_height())
        else:
            return int(self.get_roi_width())

    @width.setter
    def width(self, width):
        if self.rot90:
            self.set_roi_height(width)
        else:
            self.set_roi_width(width)

    @property
    def height(self):
        if self.rot90:
            return int(self.get_roi_width())
        else:
            return int(self.get_roi_height())

    @height.setter
    def height(self, height):
        if self.rot90:
            self.set_roi_width(height)
        else:
            self.set_roi_height(height)

    @property
    def offset_x(self):
        return self.get_roi_offset_x()

    @offset_x.setter
    def offset_x(self, offset_x):
        self.set_roi_offset_x(offset_x)

    @property
    def offset_y(self):
        return self.get_roi_offset_y()

    @offset_y.setter
    def offset_y(self, offset_y):
        self.set_roi_offset_y(offset_y)

    @property
    def gain(self):
        return self.get_gain()

    @gain.setter
    def gain(self, gain):
        self.set_gain(gain)

    @property
    def sensor_width(self):
        if self.rot90:
            return self.get_sensor_height()
        else:
            return self.get_sensor_width()

    @property
    def sensor_height(self):
        if self.rot90:
            return self.get_sensor_width()
        else:
            return self.get_sensor_height()

    def start_acquisition(self):
        """Start acquisition sequence on the camera."""
        raise NotImplementedError()

    def end_acquisition(self):
        """End acquisition sequence on the camera."""
        raise NotImplementedError()

    def capture_image(self):
        """Capture an image on the camera and return it."""
        raise NotImplementedError()

    def get_roi_width(self):
        """Get the width of the ROI on the camera."""
        raise NotImplementedError()

    def set_roi_width(self, width):
        """Set the width of the ROI on the camera."""
        raise NotImplementedError()

    def get_roi_height(self):
        """Get the height of the ROI on the camera."""
        raise NotImplementedError()

    def set_roi_height(self, height):
        """Set the height of the ROI on the camera."""
        raise NotImplementedError()

    def get_roi_offset_x(self):
        """Get the x-offset of the ROI on the camera."""
        raise NotImplementedError()

    def set_roi_offset_x(self, offset_x):
        """Set the x-offset of the ROI on the camera."""
        raise NotImplementedError()

    def get_roi_offset_y(self):
        """Get the y-offset of the ROI on the camera."""
        raise NotImplementedError()

    def set_roi_offset_y(self, offset_y):
        """Set the y-offset of the ROI on the camera."""
        raise NotImplementedError()

    def get_sensor_width(self):
        """Get the width of the camera sensor."""
        raise NotImplementedError()

    def get_sensor_height(self):
        """Get the height of the camera sensor."""
        raise NotImplementedError()

    def get_exposure_time(self):
        """Get the exposure time on the camera."""
        raise NotImplementedError()

    def set_exposure_time(self, exposure_time):
        """Set the exposure time on the camera."""
        raise NotImplementedError()

    def get_gain(self):
        """Get the gain on the camera."""
        raise NotImplementedError()

    def set_gain(self, gain):
        """Set the gain on the camera."""
        raise NotImplementedError()

    def get_temperature(self):
        """Get the temperature on the camera."""
        raise NotImplementedError()
