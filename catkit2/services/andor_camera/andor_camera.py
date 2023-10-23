import ctypes
import os
import threading
import numpy as np

from catkit2.testbed.service import Service

import andor3


class AndorCamera(Service):
    NUM_FRAMES_IN_BUFFER = 20

    def __int__(self):
        super().__init__('andor_camera')

        self.index = self.config['camera_index']

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

        # Initialize the library
        error = lib.AT_InitialiseLibrary()
        if not error == AT_ERR.SUCCESS:
            raise AndorError(error)

    def open(self):
        # Close any currently open camera
        self.close()

        camera_handle = ctypes.c_int()
        error = lib.AT_Open(self.index, ctypes.byref(camera_handle))
        if not error == AT_ERR.SUCCESS:
            raise AndorError(error)
        self.cam = camera_handle.value

        # Set standard exposure settings
        #TODO

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        #TODO
        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES_IN_BUFFER)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], self.NUM_FRAMES_IN_BUFFER)

        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES_IN_BUFFER)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))

        # Set properties from config.
        #TODO

        self.temperature_thread = threading.Thread(target=self.monitor_temperature)
        self.temperature_thread.start()

    def close(self):
        self.temperature_thread.join()

        if not self.camera_handle == AT_HANDLE.UNINITIALISED:
            error = lib.AT_Close(self.camera_handle)
            if not error == AT_ERR.SUCCESS:
                raise AndorError(error)
            self.camera_handle = AT_HANDLE.UNINITIALISED
            self.cam = None
            lib.AT_FinaliseLibrary()

    def main(self):
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def acquisition_loop(self):
        # Make sure the data stream has the right size and datatype.
        #TODO
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])

        error = lib.AT_Command(self.cam, "AcquisitionStart")
        if not error == AT_ERR.SUCCESS:
            raise AndorError(error)
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))

        try:
            while self.should_be_acquiring.is_set() and not self.should_shut_down:
                #TODO
                img = None

                self.images.submit_data(img.astype('float32'))
        finally:
            # Stop acquisition.
            lib.AT_Command(self.came, "AcquisitionStop")
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))
            self.flush()

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
        return lib.AT_GetFloat(self.cam, "SensorTemperature")

    def flush(self):
        error = lib.AT_Flush(self.cam)
        if not error == AT_ERR.SUCCESS:
            raise AndorError(error)


if __name__ == '__main__':
    service = AndorCamera()
    service.run()
