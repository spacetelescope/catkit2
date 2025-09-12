'''
This module contains a service for Allied Vision cameras.

This service is a wrapper around the Vimba X SDK.
It provides a simple interface to control the camera and acquire images.
'''

from __future__ import annotations
import contextlib

from catkit2.base_services.camera import CameraService

from vmbpy import (AllocationMode,
                   Camera, Frame, Stream,
                   FrameStatus,
                   PixelFormat,
                   VmbSystem,
                   VmbCameraError
)


class AlliedVisionCamera(CameraService):
    def __init__(self, exit_stack: contextlib.ExitStack):
        '''
        Create a new AlliedVisionCamera service.

        Parameters
        ----------
        exit_stack : contextlib.ExitStack
            The exit stack to which this service should be added.
            This is used to ensure that resources are properly cleaned up when the service is closed.
        '''
        super().__init__('allied_vision_camera_v2')
        self.exit_stack = exit_stack

        # dictionary to store the pixel format and the corresponding numpy dtype and vimba pixel format
        self.pixel_formats = {
            "Mono8": PixelFormat.Mono8,
            "Mono12": PixelFormat.Mono12,
            "Mono12Packed": PixelFormat.Mono12Packed,
            "Mono14": PixelFormat.Mono14,
            "Mono16": PixelFormat.Mono16,
        }
        self.current_pixel_format = None

    def open(self):
        pass

    def close(self):
        pass

    def start_acquisition(self):
        pass

    def end_acquisition(self):
        pass

    def capture_image(self):
        pass

    def get_roi_width(self):
        pass

    def set_roi_width(self, width):
        pass

    def get_roi_height(self):
        pass

    def set_roi_height(self, height):
        pass

    def get_roi_offset_x(self):
        pass

    def set_roi_offset_x(self, offset_x):
        pass

    def get_roi_offset_y(self):
        pass

    def set_roi_offset_y(self, offset_y):
        pass

    def get_sensor_width(self):
        pass

    def get_sensor_height(self):
        pass

    def get_exposure_time(self):
        pass

    def set_exposure_time(self, exposure_time):
        pass

    def get_gain(self):
        pass

    def set_gain(self, gain):
        pass

    def get_temperature(self):
        '''
        Get the temperature of the camera.

        This function gets the temperature of the camera.

        Returns
        -------
        float:
            The temperature of the camera in degrees Celsius.
        '''
        return self.cam.DeviceTemperature.get()


if __name__ == '__main__':
    with contextlib.ExitStack() as main_exit_stack:
        service = AlliedVisionCamera(main_exit_stack)
        service.run()
