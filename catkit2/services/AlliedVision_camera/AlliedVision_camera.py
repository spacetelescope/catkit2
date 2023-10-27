import threading
import time
import os
import numpy as np

from catkit2.testbed.service import Service

from vimba import *

class AlliedVisionCamera(Service):

    NUM_FRAMES = 20


    def __init__(self):
        super().__init__('AlliedVision_camera')

        self.should_be_aquiring = threading.Event()
        self.should_be_aquiring.set()

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
                self.images      = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES_IN_BUFFER)
                self.temperature = self.make_data_stream('temperature', 'float64', [1], self.NUM_FRAMES_IN_BUFFER)

                self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES_IN_BUFFER)
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
                while not self.should_shut_down:
                    if self.should_be_acquiring.wait(0.05):

                        cam.start_streaming(handler=acquisition_loop, buffer_count=NUM_FRAMES)

            def close(self):
                ##close cam AV

            def acquisition_loop(self, cam, frame):
                # Make sure the data stream has the right size and datatype.
                has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])

                if not has_correct_parameters:

                    self.images.update_parameters('float32', [self.height, self.width], self.NUM_FRAMES_IN_BUFFER)

                try:
                    while self.should_be_acquiring.is_set() and not self.should_shut_down:

                        if frame.get_status()== FrameStatus.Complete:
                            frame.convert_pixel_format(PixelFormat.Mono8) # TODO change
                            self.images.submit_data( frame.as_numpy_ndarray().astype('float32') )


                finally:
                    # Stop acquisition.
                    self.is_acquiring.submit_data(np.array([0], dtype='int8'))
