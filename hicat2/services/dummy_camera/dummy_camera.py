# Disable the Fortran Ctrl-C handler as it interferes with safe closing of
# the service.
import os
os.environ['FOR_DISABLE_CONSOLE_CTRL_HANDLER'] = '1'

from hicat2.protocol.service import Service, parse_service_args

import time
from hcipy import *
import numpy as np

class DummyCamera(Service):
    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'dummy_camera', testbed_port)

        config = self.configuration

        self.exposure_time = config['exposure_time']
        self.gain = config['gain']
        self._width = config['width']
        self._height = config['height']
        self._offset_x = config['offset_x']
        self._offset_y = config['offset_y']

        self.flux = config['flux']
        self.sensor_width = config['sensor_width']
        self.sensor_height = config['sensor_height']

        self.shutdown_flag = False

        self.pupil_grid = make_pupil_grid(128)
        self.aperture = evaluate_supersampled(make_hicat_aperture(True), self.pupil_grid, 4)
        self.wf = Wavefront(self.aperture)
        self.wf.total_power = 1

        self.is_acquiring = False
        self.should_be_acquiring = True

        self.images = DataStream.create('images', self.name, 'uint16', [self.sensor_height, self.sensor_width], 20)
        self.register_data_stream(self.images)

        # Create properties
        def register_property_helper(name, read_only=False):
            if read_only:
                self.register_property(Property(name, lambda: getattr(self, name)))
            else:
                self.register_property(Property(name, lambda: getattr(self, name), lambda val: setattr(self, name, val)))

        register_property_helper('exposure_time')
        register_property_helper('gain')

        register_property_helper('width')
        register_property_helper('height')
        register_property_helper('offset_x')
        register_property_helper('offset_y')

        register_property_helper('temperature', read_only=True)
        register_property_helper('sensor_width', read_only=True)
        register_property_helper('sensor_height', read_only=True)

        register_property_helper('device_name', read_only=True)
        register_property_helper('is_acquiring', read_only=True)

        self.register_command(Command('start_acquisition', self.start_acquisition))
        self.register_command(Command('end_acquisition', self.end_acquisition))

    def get_image(self):
        try:
            focal_grid = make_focal_grid(8, np.array([self.sensor_width, self.sensor_height]) / 16)
            #focal_grid = focal_grid.shifted([-self._offset_x / 8, -self._offset_y / 8])

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
        while not self.shutdown_flag:
            if not self.should_be_acquiring:
                time.sleep(0.001)
                continue

            self.acquisition_loop()

    def acquisition_loop(self):
        self.is_acquiring = True

        while self.should_be_acquiring and not self.shutdown_flag:
            img = self.get_image()

            # Make sure the data stream has the right size and datatype.
            has_correct_parameters = np.allclose(self.images.shape, img.shape)

            if not has_correct_parameters:
                self.images.update_parameters('uint16', img.shape, 20)

            frame = self.images.request_new_frame()
            frame.data[:] = img
            self.images.submit_frame(frame.id)

        self.is_acquiring = False

    def start_acquisition(self):
        self.should_be_acquiring = True

    def end_acquisition(self):
        self.should_be_acquiring = False

    def shut_down(self):
        self.shutdown_flag = True

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

    @property
    def temperature(self):
        return np.sin(2 * np.pi * time.time() / 10)

    @property
    def device_name(self):
        return 'Dummy Camera'

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    try:
        service = DummyCamera(service_name, testbed_port)
        service.run()
    finally:
        print('ending')
