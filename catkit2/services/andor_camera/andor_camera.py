import ctypes
import threading
import numpy as np

from catkit2.testbed.service import Service

try:
    __ANDOR_SDK3 = 'ANDOR_SDK3'
    __env_filename = os.getenv(__ANDOR_SDK3)

    if not __env_filename:
        raise OSError(f"Environment variable '{__ANDOR_SDK3}' doesn't exist. Create and point to Andor SDK3")

    if not os.path.exists(__env_filename):
        raise OSError(f"File not found: '{__ANDOR_SDK3}' -> '{__env_filename}'")

    andor = ctypes.cdll.LoadLibrary(__env_filename)
except Exception as error:
    raise ImportError(f"Failed to load {__ANDOR_SDK3}") from error


class AndorCamera(Service):
    NUM_FRAMES_IN_BUFFER = 20

    def __int__(self):
        super().__init__('andor_camera')

        self.index = self.config['camera_index']

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

        # Create lock for camera access
        self.mutex = threading.Lock()

    def open(self):
        # Make sure the camera is stopped
        self.close()

        andor.AT_InitialiseLibrary()
        self.cam = andor.AT_Open(self.index)

        # Set standard exposure settings

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES_IN_BUFFER)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], self.NUM_FRAMES_IN_BUFFER)

        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES_IN_BUFFER)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))

        # Set properties from config.

        self.temperature_thread = threading.Thread(target=self.monitor_temperature)
        self.temperature_thread.start()

    def close(self):
        self.temperature_thread.join()

        if self.cam is not None:
            andor.AT_Close(self.cam)
        self.cam = None
        andor.AT_FinaliseLibrary()

    def main(self):
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def acquisition_loop(self):
        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])

        # Start the acquisition
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))

    def monitor_temperature(self):
        while not self.should_shut_down:
            temperature = self.get_temperature()
            self.temperature.submit_data(np.array([temperature]))

            self.sleep(1)

    def start_acquisition(self):
        self.should_be_acquiring.set()

    def end_acquisition(self):
        self.should_be_acquiring.clear()

    def get_temperature(self):
        with self.mutex:
            temperature = None
            return temperature


if __name__ == '__main__':
    service = AndorCamera()
    service.run()
