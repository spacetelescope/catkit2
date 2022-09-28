from catkit2.testbed.service import Service

import time
from hcipy import *
import numpy as np
import threading

class DummyCamera(Service):
    def __init__(self):
        super().__init__('dummy_camera')

        self.exposure_time = self.config['exposure_time']
        self.gain = self.config['gain']
        self._width = self.config['width']
        self._height = self.config['height']
        self._offset_x = self.config['offset_x']
        self._offset_y = self.config['offset_y']

        self.flux = self.config['flux']
        self.sensor_width = self.config['sensor_width']
        self.sensor_height = self.config['sensor_height']

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

        self.pupil_grid = make_pupil_grid(128)
        self.aperture = evaluate_supersampled(make_hicat_aperture(True), self.pupil_grid, 4)
        self.wf = Wavefront(self.aperture)
        self.wf.total_power = 1

        self.images = self.make_data_stream('images', 'uint16', [self.sensor_height, self.sensor_width], 20)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], 20)

        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], 20)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))
        # self.is_acquiring.submit_data(np.array([0], dtype='int8'))

        self.temperature_thread = threading.Thread(target=self.monitor_temperature)
        self.temperature_thread.start()

        # Create properties
        def make_property_helper(name, read_only=False):
            if read_only:
                self.make_property(name, lambda: getattr(self, name))
            else:
                self.make_property(name, lambda: getattr(self, name), lambda val: setattr(self, name, val))

        make_property_helper('exposure_time')
        make_property_helper('gain')

        make_property_helper('width')
        make_property_helper('height')
        make_property_helper('offset_x')
        make_property_helper('offset_y')

        make_property_helper('sensor_width', read_only=True)
        make_property_helper('sensor_height', read_only=True)

        make_property_helper('device_name', read_only=True)
        self.make_command('repeater', self.repeater)

        self.make_command('start_acquisition', self.start_acquisition)
        self.make_command('end_acquisition', self.end_acquisition)

    def get_image(self):
        try:
            focal_grid = make_focal_grid(8, np.array([self.sensor_width, self.sensor_height]) / 16)
            # focal_grid = focal_grid.shifted([-self._offset_x / 8, -self._offset_y / 8])

            prop = FraunhoferPropagator(self.pupil_grid, focal_grid)
            img = prop(self.wf).power.shaped

            img = img[self._offset_y:self._offset_y + self._height, self._offset_x:self._offset_x + self._width]

            img = img * self.flux * self.exposure_time / 1e6

            img = large_poisson(img)
            img = np.clip(img, 0, 2**16 - 1).astype('uint16')
        except Exception as e:
            print(e)

        return img

    def main(self):
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def acquisition_loop(self):
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))

        while self.should_be_acquiring.is_set() and not self.should_shut_down:
            img = self.get_image()

            # Make sure the data stream has the right size and datatype.
            has_correct_parameters = np.allclose(self.images.shape, img.shape)

            if not has_correct_parameters:
                self.images.update_parameters('uint16', img.shape, 20)

            frame = self.images.request_new_frame()
            frame.data[:] = img
            self.images.submit_frame(frame.id)

        self.is_acquiring.submit_data(np.array([0], dtype='int8'))

    def monitor_temperature(self):
        while not self.should_shut_down:
            temperature = self.get_temperature()
            self.temperature.submit_data(np.array([temperature]))

            self.sleep(0.1)

    def start_acquisition(self):
        self.should_be_acquiring.set()

    def end_acquisition(self):
        self.should_be_acquiring.clear()

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, width):
        if width + self.offset_x > self.sensor_width:
            self._width = self.sensor_width - self.offset_x
            raise ValueError('Width larger than the sensor.')
        if width <= 0:
            self._width = 0
            raise ValueError('Width must be larger than zero.')

        self._width = width

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, height):
        if height + self.offset_y > self.sensor_height:
            self._height = self.sensor_height - self.offset_y
            raise ValueError('Height larger than the sensor.')
        if height <= 0:
            self._height = 0
            raise ValueError('Height must be larger than zero.')

        self._height = height

    @property
    def offset_x(self):
        return self._offset_x

    @offset_x.setter
    def offset_x(self, offset_x):
        if offset_x < 0:
            raise ValueError('Offset cannot be negative.')
        if offset_x + self.width > self.sensor_width:
            raise ValueError('Window is outside of the sensor.')

        self._offset_x = offset_x

    @property
    def offset_y(self):
        return self._offset_y

    @offset_y.setter
    def offset_y(self, offset_y):
        if offset_y < 0:
            raise ValueError('Offset cannot be negative.')
        if offset_y + self.height > self.sensor_height:
            raise ValueError('Window is outside of the sensor.')

        self._offset_y = offset_y

    def get_temperature(self):
        return np.sin(2 * np.pi * time.time() / 10)

    @property
    def device_name(self):
        return 'Dummy Camera'

    def repeater(self, value):
        return value

if __name__ == '__main__':
    try:
        service = DummyCamera()
        service.run()
    except Exception:
        import traceback

        print(traceback.format_exc())
        input()

