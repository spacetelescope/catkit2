import threading
import numpy as np
import contextlib

from catkit2.testbed.service import Service

from vimba import FrameStatus, PixelFormat, Vimba


class AlliedVisionCamera(Service):
    NUM_FRAMES = 20

    def __init__(self, exit_stack):
        super().__init__('allied_vision_camera')

        self.exit_stack = exit_stack

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

    def open(self):
        self.vimba = vimba.get_instance()
        self.exit_stack.enter(self.vimba)

        self.cam = self.vimba.get_all_cameras()[0]
        self.exit_stack.enter(self.cam)

        # Set device values from config file (set width and height before offsets)
        offset_x = self.config.get('offset_x', 0)
        offset_y = self.config.get('offset_y', 0)

        self.width = self.config.get('width', self.sensor_width - offset_x)
        self.height = self.config.get('height', self.sensor_height - offset_y)
        self.offset_x = offset_x
        self.offset_y = offset_y

        self.gain = self.config.get('gain', 0)
        self.exposure_time_step_size = self.config.get('exposure_time_step_size', 1)
        self.exposure_time_offset_correction = self.config.get('exposure_time_offset_correction', 0)
        self.exposure_time_base_step = self.config.get('exposure_time_base_step', 1)
        self.exposure_time = self.config.get('exposure_time', 1000)

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES)
        print(self.sensor_height)
        print(self.sensor_width)
        print(self.height)
        print(self.width)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], self.NUM_FRAMES)

        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))

        # Create properties
        def make_property_helper(name, read_only=False):
            if read_only:
                self.make_property(name, lambda: getattr(self, name))
            else:
                self.make_property(name, lambda: getattr(self, name), lambda val: setattr(self, name, val))

        make_property_helper('exposure_time')
        make_property_helper('gain')
        make_property_helper('brightness')

        make_property_helper('width')
        make_property_helper('height')
        make_property_helper('offset_x')
        make_property_helper('offset_y')

        make_property_helper('sensor_width', read_only=True)
        make_property_helper('sensor_height', read_only=True)

        make_property_helper('device_name', read_only=True)

        self.make_command('start_acquisition', self.start_acquisition)
        self.make_command('end_acquisition', self.end_acquisition)

    def main(self):
        self.cam.start_streaming(handler=self.acquisition_loop, buffer_count=self.NUM_FRAMES)
        self.cam.stop_streaming()

    def close(self):
        # close cam AV
        pass

    def acquisition_loop(self, cam, frame):
        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])

        if not has_correct_parameters:
            self.images.update_parameters('float32', [self.height, self.width], self.NUM_FRAMES)

        try:
            while self.should_be_acquiring.is_set() and not self.should_shut_down:
                if frame.get_status() == FrameStatus.Complete:
                    frame.convert_pixel_format(PixelFormat.Mono8)  # TODO change
                    print(frame.as_numpy_ndarray().astype('float32').shape)
                    self.images.submit_data(frame.as_numpy_ndarray().astype('float32'))

        finally:
            # Stop acquisition.
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))

    def start_acquisition(self):
        self.should_be_acquiring.set()

    def end_acquisition(self):
        self.should_be_acquiring.clear()

    @property
    def exposure_time(self):
        return self.cam.ExposureTime.get()

    @exposure_time.setter
    def exposure_time(self, exposure_time):
        self.cam.ExposureTime.set(exposure_time)

    @property
    def gain(self):
        return self.cam.Gain.get()

    @gain.setter
    def gain(self, gain):
        self.cam.Gain.set(gain)

    @property
    def brightness(self):
        return self.cam.Brightness.get()

    @brightness.setter
    def brightness(self, brightness):
        self.cam.Brightness.set(brightness)

    @property
    def sensor_width(self):
        return self.cam.SensorWidth.get()

    @property
    def sensor_height(self):
        return self.cam.SensorHeight.get()

    @property
    def width(self):
        return self.cam.Width.get()

    @width.setter
    def width(self, width):
        self.cam.Width.set(width)

    @property
    def height(self):
        return self.cam.Height.get()

    @height.setter
    def height(self, height):
        self.cam.Height.set(height)

    @property
    def offset_x(self):
        return self.cam.OffsetX.get()

    @offset_x.setter
    def offset_x(self, offset_x):
        self.cam.OffsetX.set(offset_x)

    @property
    def offset_y(self):
        return self.cam.OffsetY.get()

    @offset_y.setter
    def offset_y(self, offset_y):
        self.cam.OffsetY.set(offset_y)


if __name__ == '__main__':
    with contextlib.ExitStack() as exit_stack:
        service = AlliedVisionCamera(exit_stack)
        service.run()
