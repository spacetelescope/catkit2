import threading
import numpy as np

from catkit2.testbed.service import Service

from vimba import FrameStatus, PixelFormat, Vimba


class AlliedVisionCamera(Service):
    NUM_FRAMES = 20

    def __init__(self):
        super().__init__('allied_vision_camera')

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

        self.mutex = threading.Lock()

    def open(self):
        with Vimba.get_instance() as vimba:
            if len(vimba.get_all_cameras()) == 0:
                raise RuntimeError("Not a single Allied Vision camera is connected.")

            with vimba.get_all_cameras()[0] as cam:
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
                print(self.sensor_width )
                print( self.height )
                print( self.width )
                self.temperature = self.make_data_stream('temperature', 'float64', [1], self.NUM_FRAMES)

                self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES)
                self.is_acquiring.submit_data(np.array([0], dtype='int8'))

                # Create properties
                def make_property_helper(name, read_only=False, requires_stopped_acquisition=False):
                    if read_only:
                        self.make_property(name, lambda: getattr(self, name))
                    else:
                        if requires_stopped_acquisition:
                            def setter(val):
                                with StoppedAcquisition(self):
                                    setattr(self, name, val)
                        else:
                            def setter(val):
                                setattr(self, name, val)

                        self.make_property(name, lambda: getattr(self, name), setter)

                make_property_helper('exposure_time')
                make_property_helper('gain')
                make_property_helper('brightness')

                make_property_helper('width', requires_stopped_acquisition=True)
                make_property_helper('height', requires_stopped_acquisition=True)
                make_property_helper('offset_x')
                make_property_helper('offset_y')

                make_property_helper('sensor_width', read_only=True)
                make_property_helper('sensor_height', read_only=True)

                make_property_helper('device_name', read_only=True)

                self.make_command('start_acquisition', self.start_acquisition)
                self.make_command('end_acquisition', self.end_acquisition)

    def main(self):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                cam.start_streaming(handler=self.acquisition_loop, buffer_count=self.NUM_FRAMES)
                cam.stop_streaming()

    def close(self):
        ##close cam AV
        pass

    def acquisition_loop(self, cam, frame):
        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])

        if not has_correct_parameters:
            self.images.update_parameters('float32', [self.height, self.width], self.NUM_FRAMES)

        try:
            while self.should_be_acquiring.is_set() and not self.should_shut_down:
                if frame.get_status()== FrameStatus.Complete:
                    frame.convert_pixel_format(PixelFormat.Mono8) # TODO change
                    print(frame.as_numpy_ndarray().astype('float32').shape )
                    self.images.submit_data( frame.as_numpy_ndarray().astype('float32') )

        finally:
            # Stop acquisition.
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))

    def start_acquisition(self):
        self.should_be_acquiring.set()

    def end_acquisition(self):
        self.should_be_acquiring.clear()

    @property
    def exposure_time(self):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                return cam.ExposureTime.get()

    @exposure_time.setter
    def exposure_time(self, exposure_time):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                cam.ExposureTime.set( exposure_time )

    @property
    def gain(self):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                return cam.Gain.get()

    @gain.setter
    def gain(self, gain):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                cam.Gain.set( gain )

    @property
    def brightness(self):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                return cam.Brightness.get()

    @brightness.setter
    def brightness(self, brightness):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                cam.Brightness.set( brightness )

    @property
    def sensor_width(self):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                return cam.SensorWidth.get()

    @property
    def sensor_height(self):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                return cam.SensorHeight.get()

    @property
    def width(self):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                return cam.Width.get()

    @width.setter
    def width(self, width):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                cam.Width.set( width )

    @property
    def height(self):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                return cam.Height.get()

    @height.setter
    def height(self, height):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                cam.Height.set( height )

    @property
    def offset_x(self):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                return cam.OffsetX.get()

    @offset_x.setter
    def offset_x(self, offset_x):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                cam.OffsetX.set( offset_x )

    @property
    def offset_y(self):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                return cam.OffsetY.get()

    @offset_y.setter
    def offset_y(self, offset_y):
        with Vimba.get_instance() as vimba:
            with vimba.get_all_cameras()[0] as cam:
                cam.OffsetY.set( offset_y )


if __name__ == '__main__':
    service = AlliedVisionCamera()
    service.run()
