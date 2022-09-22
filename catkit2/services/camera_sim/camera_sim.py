from catkit2.testbed.service import Service

import time
import sys
import threading
import numpy as np

class CameraSim(Service):
    NUM_FRAMES_IN_BUFFER = 20

    def __init__(self):
        super().__init__('camera_sim')

        self.should_be_acquiring = threading.Event()

        # Create lock for camera access
        self.mutex = threading.Lock()

    def open(self):
        offset_x = self.config.get('offset_x', 0)
        offset_y = self.config.get('offset_y', 0)

        self.width = self.config.get('width', self.sensor_width - offset_x)
        self.height = self.config.get('height', self.sensor_height - offset_y)
        self.offset_x = offset_x
        self.offset_y = offset_y

        self.gain = self.config.get('gain', 0)
        self.exposure_time = self.config.get('exposure_time', 1000)

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES_IN_BUFFER)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], self.NUM_FRAMES_IN_BUFFER)
        self.temperature.submit_data(np.array([30.0]))

        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES_IN_BUFFER)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))

        self.make_property('width', lambda: self.width)
        self.make_property('height', lambda: self.height)
        self.make_property('offset_x', lambda: self.offset_x)
        self.make_property('offset_y', lambda: self.offset_y)

        self.make_property('exposure_time', lambda: self.exposure_time)
        self.make_property('gain', lambda: self.gain)

        self.make_command('start_acquisition', self.start_acquisition)
        self.make_command('end_acquisition', self.end_acquisition)

    def main(self):
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def acquisition_loop(self):
        self.testbed.simulator.start_camera_acquisition(at_time=0, camera_name=self.id, integration_time=self.exposure_time / 1e6, frame_interval=self.exposure_time / 1e6)
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))

        try:
            while self.should_be_acquiring.is_set() and not self.should_shut_down:

                self.should_be_acquiring.wait(0.01)
        finally:
            self.testbed.simulator.end_camera_acquisition(at_time=0, camera_name=self.id)
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))

    def start_acquisition(self):
        self.should_be_acquiring.set()

    def end_acquisition(self):
        self.should_be_acquiring.clear()

    @property
    def sensor_width(self):
        return 3000

    @property
    def sensor_height(self):
        return 2000

    @property
    def exposure_time(self):
        return self._exposure_time

    @exposure_time.setter
    def exposure_time(self, exposure_time):
        self._exposure_time = exposure_time

if __name__ == '__main__':
    service = CameraSim()
    service.run()
