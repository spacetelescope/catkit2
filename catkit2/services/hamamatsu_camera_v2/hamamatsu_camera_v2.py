"""
This module contains a service for Hamamatsu digital cameras.

This service is a wrapper around the DCAM-SDK4.
It provides a simple interface to control the camera and acquire images.
"""
from enum import Enum
import os
import sys
import threading
import numpy as np
from catkit2.base_services.camera import CameraService, StoppedAcquisition

try:
    sdk_path = os.environ.get('CATKIT_DCAM_SDK_PATH')
    if sdk_path is not None:
        sys.path.append(sdk_path)

    import dcam
except ImportError:
    print('To use Hamamatsu cameras, you need to set the CATKIT_DCAM_SDK_PATH environment variable.')
    raise


class CoolerMode(Enum):
    off = 1.0
    on = 2.0    # target temperature = -20 deg
    max = 4.0   # target temperature = -31 deg


class FanStatus(Enum):
    off = 1.0
    on = 2.0


class HamamatsuCamera(CameraService):
    NUM_FRAMES = 20

    def __init__(self):
        """
        Create a new HamamatsuCamera service.
        """
        super().__init__('hamamatsu_camera_v2')

        # Stopped acquisition flags for base class
        self.width_requires_stopped_acquisition = True
        self.height_requires_stopped_acquisition = True
        self.offset_x_requires_stopped_acquisition = True
        self.offset_y_requires_stopped_acquisition = True
        self.exposure_time_requires_stopped_acquisition = False
        self.gain_requires_stopped_acquisition = True

        # Create lock for camera access
        self.mutex = threading.Lock()

    def open(self):
        # Dictionary to store the pixel format and the corresponding numpy dtype and dcam pixel format
        self.pixel_formats = {
            "Mono8": dcam.DCAM_PIXELTYPE.MONO8,
            "Mono16": dcam.DCAM_PIXELTYPE.MONO16,
        }
        self.current_pixel_format = None

        if dcam.Dcamapi.init() is False:
            raise RuntimeError(f'Dcamapi.init() fails with error {dcam.Dcamapi.lasterr()}')

        camera_id = self.config.get('camera_id', 0)
        self.cam = dcam.Dcam(camera_id)
        self.log.info('Using camera with ID %s', camera_id)
        if self.cam.dev_open() is False:
            raise RuntimeError(f'Dcam.dev_open() fails with error {self.cam.lasterr()}')

        # Read ROI of full sensor before ROI is adapted.
        self._sensor_width = int(self.cam.prop_getvalue(dcam.DCAM_IDPROP.IMAGE_WIDTH))
        self._sensor_height = int(self.cam.prop_getvalue(dcam.DCAM_IDPROP.IMAGE_HEIGHT))

        # Set subarray mode to on so that it checks subarray compatibility when picking ROI
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.SUBARRAYMODE, 2.0)

        binning = self.config.get('binning', 1)
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.BINNING, binning)

        defect_correction = 2.0 if self.config.get('defect_correction', True) else 1.0
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.DEFECTCORRECT_MODE, defect_correction)

        self.hot_pixel_correction = self.config.get('hot_pixel_correction', 'standard')
        if self.hot_pixel_correction == "standard":
            hot_pixel_correction = 1.0
        elif self.hot_pixel_correction == "minimum":
            hot_pixel_correction = 2.0
        elif self.hot_pixel_correction == "aggressive":
            hot_pixel_correction = 3.0
        else:
            raise ValueError(f'Invalid hot pixel correction: {self.hot_pixel_correction}, must be one of ["standard", "minimum", "aggressive"]')
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.HOTPIXELCORRECT_LEVEL, hot_pixel_correction)

        self.camera_mode = self.config.get('camera_mode', "standard")
        if self.camera_mode == "ultraquiet":
            camera_mode = 1.0
        elif self.camera_mode == "standard":
            camera_mode = 2.0
        else:
            raise ValueError(f'Invalid camera mode: {self.camera_mode}, must be one of ["ultraquiet", "standard"]')
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.READOUTSPEED, camera_mode)

        self.current_pixel_format = self.config.get('pixel_format', 'Mono16')
        if self.current_pixel_format not in self.pixel_formats:
            raise ValueError(f'Invalid pixel format: {self.current_pixel_format}, must be one of {str(list(self.pixel_formats.keys()))}')
        self.log.info('Using pixel format: %s', self.current_pixel_format)
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.IMAGE_PIXELTYPE, self.pixel_formats[self.current_pixel_format])

        def make_property_helper(property_name, read_only=False, dtype=None):
            if dtype is None:
                dtype = ''

            def getter():
                return getattr(self, property_name)

            if read_only:
                self.make_property(property_name, getter, type=dtype)
                return

            def setter(value):
                setattr(self, property_name, value)

            self.make_property(property_name, getter, setter, type=dtype)

        self.critical_temperature = self.config.get('critical_temperature', 28.0)
        self.cooler_mode = self.config.get('cooling_mode', 'on')
        self.fan_status = self.config.get('fan_status', 'off')

        make_property_helper('brightness', read_only=True)
        make_property_helper('fan_status')
        make_property_helper('cooler_mode')

        super().open()

    def close(self):
        super().close()

        self.cooler_mode = 'on'
        self.cam.dev_close()
        self.cam = None

        dcam.Dcamapi.uninit()

    def start_acquisition(self):
        if self.cam.buf_alloc(self.NUM_FRAMES) is False:
            raise RuntimeError(f'Dcam.buf_alloc() fails with error {self.cam.lasterr()}')
        if self.cam.cap_start() is False:
            raise RuntimeError(f'Dcam.cap_start() fails with error {self.cam.lasterr()}')

    def end_acquisition(self):
        self.cam.cap_stop()
        self.cam.buf_release()

    def capture_image(self):
        timeout_millisec = 2000
        if self.cam.lasterr().is_timeout():
            self.log.warning('Timeout while waiting for frame')
        if self.cam.wait_capevent_frameready(timeout_millisec) is False:
            raise RuntimeError(
                f'Dcam.wait_capevent_frameready({timeout_millisec}) fails with error {self.cam.lasterr()}')

        img = self.cam.buf_getlastframedata()

        return img

    def get_roi_width(self):
        return self.cam.prop_getvalue(getattr(dcam.DCAM_IDPROP, 'SUBARRAYHSIZE'))

    def set_roi_width(self, width):
        self.cam.prop_setvalue(getattr(dcam.DCAM_IDPROP, 'SUBARRAYHSIZE'), width)

    def get_roi_height(self):
        return self.cam.prop_getvalue(getattr(dcam.DCAM_IDPROP, 'SUBARRAYVSIZE'))

    def set_roi_height(self, height):
        self.cam.prop_setvalue(getattr(dcam.DCAM_IDPROP, 'SUBARRAYVSIZE'), height)

    def get_roi_offset_x(self):
        return self.cam.prop_getvalue(getattr(dcam.DCAM_IDPROP, 'SUBARRAYVPOS'))

    def set_roi_offset_x(self, offset_x):
        self.cam.prop_setvalue(getattr(dcam.DCAM_IDPROP, 'SUBARRAYVPOS'), offset_x)

    def get_roi_offset_y(self):
        return self.cam.prop_getvalue(getattr(dcam.DCAM_IDPROP, 'SUBARRAYHPOS'))

    def set_roi_offset_y(self, offset_y):
        self.cam.prop_setvalue(getattr(dcam.DCAM_IDPROP, 'SUBARRAYHPOS'), offset_y)

    def get_sensor_width(self):
        return self._sensor_width

    def get_sensor_height(self):
        return self._sensor_height

    def get_exposure_time(self):
        return self.cam.prop_getvalue(getattr(dcam.DCAM_IDPROP, 'EXPOSURETIME')) * 1e6

    def set_exposure_time(self, exposure_time):
        self.cam.prop_setvalue(getattr(dcam.DCAM_IDPROP, 'EXPOSURETIME'), exposure_time / 1e6)

    def get_gain(self):
        return self.cam.prop_getvalue(getattr(dcam.DCAM_IDPROP, 'CONTRASTGAIN'))

    def set_gain(self, gain):
        self.cam.prop_setvalue(getattr(dcam.DCAM_IDPROP, 'CONTRASTGAIN'), gain)

    def get_temperature(self):
        """
        Get the temperature of the camera.

        This function gets the temperature of the camera.

        Returns
        -------
        float:
            The temperature of the camera in degrees Celsius.
        """
        return self.cam.prop_getvalue(dcam.DCAM_IDPROP.SENSORTEMPERATURE)

    def monitor_temperature(self):
        """
        Monitor the temperature of the camera.

        This function is a separate thread that monitors the temperature of
        the camera and submits the data to the temperature data stream.
        """
        while not self.should_shut_down:
            temperature = self.get_temperature()
            self.temperature.submit_data(np.array([temperature]))

            if temperature > self.critical_temperature and self.is_acquiring.get():
                self.log.warning(f'Camera temperature = {temperature} > {self.critical_temperature} degrees.')
                self.log.warning('Stopping acquisition and start fan.')
                self.fan_status = 'on'
                self.cooler_mode = 'on'
                self.end_acquisition()

            self.sleep(0.1)

    @property
    def brightness(self):
        return self.cam.prop_getvalue(getattr(dcam.DCAM_IDPROP, 'SENSITIVITY'))

    @property
    def fan_status(self):
        return FanStatus(self.cam.prop_getvalue(getattr(dcam.DCAM_IDPROP, 'SENSORCOOLERFAN'))).name

    @fan_status.setter
    def fan_status(self, status):
        self.cam.prop_setvalue(getattr(dcam.DCAM_IDPROP, 'SENSORCOOLERFAN'), FanStatus[status].value)

    @property
    def cooler_mode(self):
        return CoolerMode(self.cam.prop_getvalue(getattr(dcam.DCAM_IDPROP, 'SENSORCOOLER'))).name

    @cooler_mode.setter
    def cooler_mode(self, mode):
        self.cam.prop_setvalue(getattr(dcam.DCAM_IDPROP, 'SENSORCOOLER'), CoolerMode[mode].value)


if __name__ == '__main__':
    service = HamamatsuCamera()
    service.run()
