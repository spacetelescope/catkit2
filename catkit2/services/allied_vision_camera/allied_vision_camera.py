'''
This module contains a service for Allied Vision cameras.

This service is a wrapper around the Vimba SDK. It provides a simple interface to control the camera and acquire images.
'''

from __future__ import annotations
import contextlib
import threading
import time

import numpy as np

from vimba import (AllocationMode,
                   Camera, Frame,
                   FrameStatus,
                   PixelFormat,
                   Vimba,
                   VimbaCameraError
)

from catkit2.testbed.service import Service


class FrameHandler:
    '''
    This class is a callback handler for the camera.

    It is used to handle incoming frames from the camera.
    The frames are then submitted to the data stream.

    Args:
        av_camera : AlliedVisionCamera
            The AlliedVisionCamera service object to which the frames should be submitted.
    '''
    def __init__(self, av_camera: AlliedVisionCamera):
        self.av_camera = av_camera
        self.shutdown_event = threading.Event()

    def __call__(self, cam: Camera, frame: Frame):

        if not self.av_camera.should_be_acquiring.is_set() or self.av_camera.should_shut_down:
            self.shutdown_event.set()
            return

        elif frame.get_status() == FrameStatus.Complete:
            if frame.get_pixel_format() == PixelFormat.Mono12Packed:
                frame.convert_pixel_format(PixelFormat.Mono12)
            self.av_camera.images.submit_data(np.squeeze(frame.as_numpy_ndarray().astype('float32'), 2))

        cam.queue_frame(frame)


class AlliedVisionCamera(Service):
    '''
    Service for Allied Vision cameras.

    This service is a wrapper around the Vimba SDK. It provides a simple interface to control the camera and acquire images.

    Args:
        exit_stack : contextlib.ExitStack
            The exit stack to which this service should be added. This is used to ensure that resources are properly cleaned up when the service is closed.
    '''
    NUM_FRAMES = 20

    def __init__(self, exit_stack: contextlib.ExitStack):
        super().__init__('allied_vision_camera')

        self.vimba = None
        self.cam = None
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
        self.temperature_thread = None
        self.temperature = None
        self.images = None
        self.is_acquiring = None

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

    def open(self):
        self.vimba = Vimba.get_instance()
        self.exit_stack.enter_context(self.vimba)

        # convert int to IPv4 address
        def int_to_ip(int_ip):
            return '.'.join([str(int_ip >> i & 0xff) for i in [24, 16, 8, 0]])

        # cams = self.vimba.get_all_cameras()
        # self.log.debug('Cameras found: {}'.format(len(cams)))
        # for cam in cams:
        #     self.log.debug('/// Camera Name   : {}'.format(cam.get_name()))
        #     self.log.debug('/// Camera ID     : {}'.format(cam.get_id()))
        #     with cam:
        #         self.log.debug(
        #           '/// Camera IP     : {}'.format(int_to_ip(cam.GevCurrentIPAddress.get())))

        camera_id = self.config.get('camera_id', 0)
        self.log.info('Using camera with ID %s', camera_id)

        try:
            self.cam = self.vimba.get_camera_by_id(camera_id)
        except VimbaCameraError as e:
            raise RuntimeError(
                f'Could not find camera with ID {camera_id}') from e
        self.exit_stack.enter_context(self.cam)

        self.log.debug('Camera Name: %s', self.cam.get_name())
        self.log.debug('Camera Model: %s', self.cam.get_model())
        self.log.debug('Camera ID: %s', self.cam.get_id())
        self.log.debug('Camera IP: %s', int_to_ip(self.cam.GevCurrentIPAddress.get()))

        self.current_pixel_format = self.config.get('pixel_format', 'Mono8')
        if self.current_pixel_format not in self.pixel_formats:
            raise ValueError('Invalid pixel format: ' +
                             self.current_pixel_format +
                             ', must be one of ' +
                             str(list(self.pixel_formats.keys())))
        self.log.debug('Using pixel format: %s', self.current_pixel_format)
        self.cam.set_pixel_format(self.pixel_formats[self.current_pixel_format])

        # Set device values from config file (set width and height before offsets)
        offset_x = self.config.get('offset_x', 0)
        offset_y = self.config.get('offset_y', 0)

        self.width = self.config.get('width', self.sensor_width - offset_x)
        self.height = self.config.get('height', self.sensor_height - offset_y)
        self.offset_x = offset_x
        self.offset_y = offset_y

        self.gain = self.config.get('gain', 0)
        self.exposure_time = self.config.get('exposure_time', 1000)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], 20)


        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES)

        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))

        # Create properties
        def make_property_helper(name, read_only=False):
            if read_only:
                self.make_property(name, lambda: getattr(self, name))
            else:
                self.make_property(name, lambda: getattr(self, name), lambda val: setattr(self, name, val))

        make_property_helper('exposure_time')
        make_property_helper('gain')
        make_property_helper('brightness')

        make_property_helper('width')
        make_property_helper('height')
        make_property_helper('offset_x')
        make_property_helper('offset_y')

        make_property_helper('sensor_width', read_only=True)
        make_property_helper('sensor_height', read_only=True)

        make_property_helper('device_name', read_only=True)

        self.make_command('start_acquisition', self.start_acquisition)
        self.make_command('end_acquisition', self.end_acquisition)

        self.temperature_thread = threading.Thread(target=self.monitor_temperature)
        self.temperature_thread.start()

    def main(self):
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def close(self):
        self.cam = None

    def acquisition_loop(self):
        '''
        The main acquisition loop.

        This function is the main loop for acquiring images from the camera.
        It starts the acquisition and then waits for incoming frames.
        '''
        # Start acquisition.
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))
        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])
        if not has_correct_parameters:
            self.images.update_parameters('float32', [self.height, self.width], self.NUM_FRAMES)

        frame_handler = FrameHandler(self)
        try:
            self.cam.start_streaming(handler=frame_handler, buffer_count=self.NUM_FRAMES,
                                     allocation_mode=AllocationMode.AllocAndAnnounceFrame)
            frame_handler.shutdown_event.wait()
        finally:
            # Stop acquisition.
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))
            self.cam.stop_streaming()

    def monitor_temperature(self):
        while not self.should_shut_down:
            temperature = self.get_temperature()
            self.temperature.submit_data(np.array([temperature]))

            self.sleep(0.1)

    def start_acquisition(self):
        self.should_be_acquiring.set()

    def end_acquisition(self):
        self.should_be_acquiring.clear()

    def get_temperature(self):
        return np.sin(2 * np.pi * time.time() / 10)  # TODO: replace with real function

    @property
    def exposure_time(self):
        '''
        The exposure time in microseconds.

        This property can be used to get the exposure time of the camera.

        Returns:
            int: The exposure time in microseconds.
        '''
        try:
            # This is the old way of setting the exposure time.
            return self.cam.ExposureTime.get()
        except AttributeError:
            # This is the new way of setting the exposure time.
            return self.cam.ExposureTimeAbs.get()

    @exposure_time.setter
    def exposure_time(self, exposure_time: int):
        '''
        Set the exposure time in microseconds.

        This property can be used to set the exposure time of the camera.

        Args:
            exposure_time : int
                The exposure time in microseconds.
        '''
        try:
            # This is the old way of getting the exposure time.
            self.cam.ExposureTime.set(exposure_time)
        except AttributeError:
            # This is the new way of getting the exposure time.
            self.cam.ExposureTimeAbs.set(exposure_time)

    @property
    def gain(self):
        '''
        The gain of the camera.

        This property can be used to get the gain of the camera.

        Returns:
            int: The gain of the camera.
        '''
        return self.cam.Gain.get()

    @gain.setter
    def gain(self, gain: int):
        '''
        Set the gain of the camera.

        This property can be used to set the gain of the camera.

        Args:
            gain : int
                The gain of the camera.
        '''
        self.cam.Gain.set(gain)

    @property
    def brightness(self):
        '''
        The brightness of the camera.

        This property can be used to get the brightness of the camera.

        Returns:
            int: The brightness of the camera.
        '''
        return self.cam.Brightness.get()

    @brightness.setter
    def brightness(self, brightness: int):
        '''
        Set the brightness of the camera.

        This property can be used to set the brightness of the camera.

        Args:
            brightness : int
                The brightness of the camera.
        '''
        self.cam.Brightness.set(brightness)

    @property
    def sensor_width(self):
        '''
        The width of the sensor in pixels.

        This property can be used to get the width of the sensor in pixels.

        Returns:
            int: The width of the sensor in pixels.
        '''
        return self.cam.SensorWidth.get()

    @property
    def sensor_height(self):
        '''
        The height of the sensor in pixels.

        This property can be used to get the height of the sensor in pixels.

        Returns:
            int: The height of the sensor in pixels.
        '''
        return self.cam.SensorHeight.get()

    @property
    def width(self):
        '''
        The width of the image in pixels.

        This property can be used to get the width of the image in pixels.

        Returns:
            int: The width of the image in pixels.
        '''
        return self.cam.Width.get()

    @width.setter
    def width(self, width: int):
        '''
        Set the width of the image in pixels.

        This property can be used to set the width of the image in pixels.

        Args:
            width : int
                The width of the image in pixels.
        '''
        self.cam.Width.set(width)

    @property
    def height(self):
        '''
        The height of the image in pixels.

        This property can be used to get the height of the image in pixels.

        Returns:
            int: The height of the image in pixels.
        '''
        return self.cam.Height.get()

    @height.setter
    def height(self, height: int):
        '''
        Set the height of the image in pixels.

        This property can be used to set the height of the image in pixels.

        Args:
            height : int
                The height of the image in pixels.
        '''
        self.cam.Height.set(height)

    @property
    def offset_x(self):
        '''
        The x offset of the image in pixels.

        This property can be used to get the x offset of the image in pixels.

        Returns:
            int: The x offset of the image in pixels.
        '''
        return self.cam.OffsetX.get()

    @offset_x.setter
    def offset_x(self, offset_x: int):
        '''
        Set the x offset of the image in pixels.

        This property can be used to set the x offset of the image in pixels.

        Args:
            offset_x : int
                The x offset of the image in pixels.
        '''
        self.cam.OffsetX.set(offset_x)

    @property
    def offset_y(self):
        '''
        The y offset of the image in pixels.

        This property can be used to get the y offset of the image in pixels.

        Returns:
            int: The y offset of the image in pixels.
        '''
        return self.cam.OffsetY.get()

    @offset_y.setter
    def offset_y(self, offset_y: int):
        '''
        Set the y offset of the image in pixels.

        This property can be used to set the y offset of the image in pixels.

        Args:
            offset_y : int
                The y offset of the image in pixels.
        '''
        self.cam.OffsetY.set(offset_y)


if __name__ == '__main__':
    with contextlib.ExitStack() as main_exit_stack:
        service = AlliedVisionCamera(main_exit_stack)
        service.run()
