import threading
import numpy as np
import contextlib
import time

from catkit2.testbed.service import Service

import vimba


class FrameHandler:
    def __init__(self, av_camera):
        self.av_camera = av_camera
        self.shutdown_event = threading.Event()

    def __call__(self, cam, frame):

        if not self.av_camera.should_be_acquiring.is_set():
            self.shutdown_event.set()
            return

        elif frame.get_status() == vimba.FrameStatus.Complete:
            frame.convert_pixel_format(vimba.PixelFormat.Mono8)  # TODO change
            self.av_camera.images.submit_data(np.squeeze(frame.as_numpy_ndarray().astype('float32'), 2))

        cam.queue_frame(frame)


class AlliedVisionCamera(Service):
    NUM_FRAMES = 20

    def __init__(self, exit_stack):
        super().__init__('allied_vision_camera')

        self.exit_stack = exit_stack

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

    def open(self):
        self.vimba = vimba.Vimba.get_instance()
        self.exit_stack.enter_context(self.vimba)

        camera_id = self.config.get('camera_id', 0)
        try:
            self.cam = self.vimba.get_camera_by_id(camera_id)
        except vimba.VimbaCameraError:
            raise RuntimeError(f'Could not find camera with ID {camera_id}')
        self.exit_stack.enter_context(self.cam)

        # Set device values from config file (set width and height before offsets)
        offset_x = self.config.get('offset_x', 0)
        offset_y = self.config.get('offset_y', 0)

        self.width = self.config.get('width', self.sensor_width - offset_x)
        self.height = self.config.get('height', self.sensor_height - offset_y)
        self.offset_x = offset_x
        self.offset_y = offset_y

        self.gain = self.config.get('gain', 0)
        self.exposure_time = self.config.get('exposure_time', 1000)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], 20)


        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES)

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

        self.temperature_thread = threading.Thread(target=self.monitor_temperature)
        self.temperature_thread.start()

    def main(self):
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def close(self):
        self.cam = None

    def acquisition_loop(self):

        # Start acquisition.
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))
        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])
        if not has_correct_parameters:
            self.images.update_parameters('float32', [self.height, self.width], self.NUM_FRAMES)

        frame_handler = FrameHandler(self)
        try:
            if self.should_be_acquiring.is_set() and not self.should_shut_down:
                self.cam.start_streaming(handler=frame_handler, buffer_count=self.NUM_FRAMES)
                frame_handler.shutdown_event.wait()
        finally:
            # Stop acquisition.
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))
            self.cam.stop_streaming()

    def monitor_temperature(self):
        while not self.should_shut_down:
            temperature = self.get_temperature()
            self.temperature.submit_data(np.array([temperature]))

            self.sleep(0.1)

    def start_acquisition(self):
        self.should_be_acquiring.set()

    def end_acquisition(self):
        self.should_be_acquiring.clear()

    def get_temperature(self):
       return np.sin(2 * np.pi * time.time() / 10)

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
