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

    def open(self):
        self.cam = andor3.Andor3()
        self.cam.open(self.index)

        self.initialize_cooling()

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

        self.make_command('start_acquisition', self.start_acquisition)
        self.make_command('end_acquisition', self.end_acquisition)

        self.temperature_thread = threading.Thread(target=self.monitor_temperature)
        self.temperature_thread.start()

    def close(self):
        self.temperature_thread.join()

        self.cam.close()

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
            self.cam.flush()

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
        return self.cam.SensorTemperature

    def initialize_cooling(self):
        # Set requested temperature to -35C, turn on sensor cooling and turn off fan
        self.cam.TemperatureControl = 4
        self.cam.SensorCooling = True
        self.cam.FanSpeed = 0

    @property
    def width(self):
        return self.cam.AOIWidth

    @width.setter
    def width(self, value):
        self.cam.AOIWidth = value

    @property
    def height(self):
        return self.cam.AOIHeight

    @height.setter
    def height(self, value):
        self.cam.AOIHeight = value

    @property
    def sensor_width(self):
        pass

    @sensor_width.setter
    def sensor_width(self, value):
        pass

    @property
    def sensor_height(self):
        pass

    @sensor_height.setter
    def sensor_height(self, value):
        pass

    @property
    def offset_x(self):
        return self.cam.AOITop

    @offset_x.setter
    def offset_x(self, value):
        self.cam.AOITop = value

    @property
    def offset_y(self):
        return self.cam.AOILeft

    @offset_y.setter
    def offset_y(self, value):
        self.cam.AOILeft = value


if __name__ == '__main__':
    service = AndorCamera()
    service.run()
