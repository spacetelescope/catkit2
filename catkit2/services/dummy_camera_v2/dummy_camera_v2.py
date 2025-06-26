import time
import numpy as np
import threading
from hcipy import *

import os
import numpy as np

from catkit2.base_services import CameraService

class DummyCamera(CameraService):
    def __init__(self):
        super().__init__('dummy_camera_v2')
        
        self.log.debug('Dummy camera service started')

        self.pupil_grid = make_pupil_grid(128)
        self.aperture = evaluate_supersampled(make_hicat_aperture(True), self.pupil_grid, 4)
        self.wf = Wavefront(self.aperture)
        self.wf.total_power = 1
    
    def open(self):
        # Set up gerneal camera properties.
        super().open()

    def close(self):
        super().close()
        self.camera.close()

    # TODO - write all functions in here
    def start_acquisition(self):
        # TODO - write a function to start the acquisition
        self.should_be_acquiring.set()
        pass

    def end_acquisition(self):
        # TODO - write a function to start the acquisition
        self.should_be_acquiring.clear()
        pass

    def monitor_temperature(self):
        while not self.should_shut_down:
            self.log.debug('Monitoring temperature')
            temperature = self.get_temperature()
            self.temperature.submit_data(np.array([temperature]))
            self.sleep(0.1)

    def get_temperature(self):
        return np.sin(2 * np.pi * time.time() / 10)

    def get_roi_width(self): # get from the sensor space
        return self.config['width']

    def set_roi_width(self, width):
        return width
        
    def get_roi_height(self):
        return self.config['height']

    def set_roi_height(self, height):
        return height

    def get_roi_offset_x(self):
        pass

    def set_roi_offset_x(self, offset_x):
        pass

    def get_roi_offset_y(self):
        pass

    def set_roi_offset_y(self, offset_y):
        pass

    def get_sensor_width(self):
        return self.config['sensor_width']

    def get_sensor_height(self):
        return self.config['sensor_height']

    def get_exposure_time(self):
        pass

    def set_exposure_time(self, exposure_time):
        pass

    def get_gain(self):
        pass

    def set_gain(self, gain):
        pass

if __name__ == '__main__':
    try:
        service = DummyCamera()
        service.run()

    except Exception:
        import traceback

        print(traceback.format_exc())
        input()

