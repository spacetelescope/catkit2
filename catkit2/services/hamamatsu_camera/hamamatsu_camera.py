"""
This module contains a service for Hamamatsu digital cameras.

This service is a wrapper around the DCAM-SDK4.
It provides a simple interface to control the camera and acquire images.
"""
import os
import sys
import threading
import numpy as np
from catkit2.testbed.service import Service

try:
    sdk_path = os.environ.get('CATKIT_DCAM_SDK_PATH')
    if sdk_path is not None:
        sys.path.append(sdk_path)

    import dcam
except ImportError:
    print('To use Hamamatsu cameras, you need to set the CATKIT_DCAM_SDK_PATH environment variable.')
    raise


class HamamatsuCamera(Service):
    """
    Service for Hamamatsu cameras.

    This service is a wrapper around the DCAM-SDK4.
    It provides a simple interface to control the camera and acquire images.

    Attributes
    ----------
    cam : Camera
        The camera to control.
    pixel_formats : dict
        A dictionary to store the pixel format and the corresponding numpy dtype and dcam pixel format.
    current_pixel_format : str
        The current pixel format to use.
    temperature_thread : threading.Thread
        A thread to monitor the temperature of the camera.
    temperature : DataStream
        A data stream to submit the temperature of the camera.
    images : DataStream
        A data stream to submit the images from the camera.
    is_acquiring : DataStream
        A data stream to submit whether the camera is currently acquiring images.
    should_be_acquiring : threading.Event
        An event to signal whether the camera should be acquiring images.
    NUM_FRAMES : int
        The number of frames to allocate for the data streams.
    """
    NUM_FRAMES = 20

    def __init__(self):
        """
        Create a new HamamatsuCamera service.
        """
        super().__init__('hamamatsu_camera')

        self.cam = None

        # Dictionary to store the pixel format and the corresponding numpy dtype and dcam pixel format
        self.pixel_formats = {
            "Mono8": dcam.DCAM_PIXELTYPE.MONO8,
            "Mono16": dcam.DCAM_PIXELTYPE.MONO16,
        }
        self.current_pixel_format = None
        self.temperature_thread = None
        self.temperature = None
        self.images = None
        self.is_acquiring = None

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

    def open(self):
        """
        Open the service.

        This function is called when the service is opened.
        It initializes the camera and creates the data streams and properties.

        Raises
        ------
        ValueError
            If the pixel format is invalid.
        RuntimeError
            For a Dcamapi or Dcam error when initializing the library or when opening the camera.
        """
        if dcam.Dcamapi.init() is False:
            raise RuntimeError(f'Dcamapi.init() fails with error {dcam.Dcamapi.lasterr()}')

        camera_id = self.config.get('camera_id', 0)
        self.cam = dcam.Dcam(camera_id)
        self.log.info('Using camera with ID %s', camera_id)
        if self.cam.dev_open() is False:
            raise RuntimeError(f'Dcam.dev_open() fails with error {self.cam.lasterr()}')

        # Set subarray mode to on so that it checks subarray compatibility when picking ROI
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.SUBARRAYMODE, 2.0)

        # Set binning
        binning = self.config.get('binning', 1)
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.BINNING, binning)

        # Set camera mode
        camera_mode = self.config.get('camera_mode', "standard")
        if camera_mode == "ultraquiet":
            self.camera_mode = 1.0
        elif camera_mode == "standard":
            self.camera_mode = 2.0
        else:
            raise ValueError(f'Invalid camera mode: {camera_mode}, must be one of ["ultraquiet", "standard"]')
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.READOUTSPEED, self.camera_mode)

        self.current_pixel_format = self.config.get('pixel_format', 'Mono16')
        if self.current_pixel_format not in self.pixel_formats:
            raise ValueError(f'Invalid pixel format: {self.current_pixel_format}, must be one of {str(list(self.pixel_formats.keys()))}')
        self.log.info('Using pixel format: %s', self.current_pixel_format)
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.IMAGE_PIXELTYPE, self.pixel_formats[self.current_pixel_format])

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

        self.make_command('start_acquisition', self.start_acquisition)
        self.make_command('end_acquisition', self.end_acquisition)

        self.temperature_thread = threading.Thread(target=self.monitor_temperature)
        self.temperature_thread.start()

    def main(self):
        """
        The main function of the service.

        This function is called when the service is started.
        It starts the acquisition loop and waits for incoming frames.
        """
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def close(self):
        self.cam.dev_close()
        self.cam = None

        dcam.Dcamapi.uninit()

    def acquisition_loop(self):
        """
        The main acquisition loop.

        This function is the main loop for acquiring images from the camera.
        It starts the acquisition and then waits for incoming frames.
        """
        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])
        if not has_correct_parameters:
            self.images.update_parameters('float32', [self.height, self.width], self.NUM_FRAMES)

        # Start acquisition.
        if self.cam.buf_alloc(self.NUM_FRAMES) is False:
            raise RuntimeError(f'Dcam.buf_alloc() fails with error {self.cam.lasterr()}')
        if self.cam.cap_start() is False:
            raise RuntimeError(f'Dcam.cap_start() fails with error {self.cam.lasterr()}')
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))

        timeout_millisec = 2000
        try:
            while self.should_be_acquiring.is_set() and not self.should_shut_down:
                if self.cam.lasterr().is_timeout():
                    self.log.warning('Timeout while waiting for frame')
                if self.cam.wait_capevent_frameready(timeout_millisec) is False:
                    raise RuntimeError(f'Dcam.wait_capevent_frameready({timeout_millisec}) fails with error {self.cam.lasterr()}')

                if self.cam.buf_getframedata(-2) is False:
                    # If there is no second to last frame, it means we just acquired the first frame.
                    # In this case, drop the current frame since it always contains systematic errors.
                    self.log.info('Dropping first camera frame')
                    continue

                img = self.cam.buf_getlastframedata()
                self.images.submit_data(img.astype('float32'))

        finally:
            # Stop acquisition.
            self.cam.cap_stop()
            self.cam.buf_release()
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))

    def monitor_temperature(self):
        """
        Monitor the temperature of the camera.

        This function is a separate thread that monitors the temperature of
        the camera and submits the data to the temperature data stream.
        """
        while not self.should_shut_down:
            temperature = self.get_temperature()
            self.temperature.submit_data(np.array([temperature]))

            self.sleep(0.1)

    def start_acquisition(self):
        """
        Start the acquisition loop.

        This function starts the acquisition loop.
        """
        self.should_be_acquiring.set()

    def end_acquisition(self):
        """
        End the acquisition loop.

        This function ends the acquisition loop.
        """
        self.should_be_acquiring.clear()

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

    @property
    def exposure_time(self):
        """
        The exposure time in microseconds.

        This property can be used to get the exposure time of the camera.

        Returns:
        --------
        float:
            The exposure time in microseconds.
        """
        return self.cam.prop_getvalue(dcam.DCAM_IDPROP.EXPOSURETIME) * 1e6

    @exposure_time.setter
    def exposure_time(self, exposure_time: float):
        """
        Set the exposure time in microseconds.

        This property can be used to set the exposure time of the camera.

        Parameters
        ----------
        exposure_time : float
            The exposure time in microseconds.
        """
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.EXPOSURETIME, exposure_time / 1e6)

    @property
    def gain(self):
        """
        The gain of the camera.

        This property can be used to get the gain of the camera.

        Returns:
        --------
        int:
            The gain of the camera.
        """
        return self.cam.prop_getvalue(dcam.DCAM_IDPROP.CONTRASTGAIN)

    @gain.setter
    def gain(self, gain: int):
        """
        Set the gain of the camera.

        This property can be used to set the gain of the camera.

        Parameters
        ----------
        gain : int
            The gain of the camera.
        """
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.CONTRASTGAIN, gain)

    @property
    def brightness(self):
        """
        The brightness of the camera.

        This property can be used to get the brightness of the camera.

        Returns:
        --------
        int:
            The brightness of the camera.
        """
        return self.cam.prop_getvalue(dcam.DCAM_IDPROP.SENSITIVITY)

    @brightness.setter
    def brightness(self, brightness: int):
        """
        Set the brightness of the camera.

        This property can be used to set the brightness of the camera.

        Parameters
        ----------
        brightness : int
            The brightness of the camera.
        """
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.SENSITIVITY, brightness)

    @property
    def sensor_width(self):
        """
        The width of the sensor in pixels.

        This property can be used to get the width of the sensor in pixels.

        Returns:
        --------
        int:
            The width of the sensor in pixels.
        """
        return int(self.cam.prop_getvalue(dcam.DCAM_IDPROP.IMAGE_WIDTH))

    @property
    def sensor_height(self):
        """
        The height of the sensor in pixels.

        This property can be used to get the height of the sensor in pixels.

        Returns:
        --------
        int:
            The height of the sensor in pixels.
        """
        return int(self.cam.prop_getvalue(dcam.DCAM_IDPROP.IMAGE_HEIGHT))

    @property
    def width(self):
        """
        The width of the image in pixels.

        This property can be used to get the width of the image in pixels.

        Returns:
        --------
        int:
            The width of the image in pixels.
        """
        return int(self.cam.prop_getvalue(dcam.DCAM_IDPROP.SUBARRAYHSIZE))

    @width.setter
    def width(self, width: int):
        """
        Set the width of the image in pixels.

        This property can be used to set the width of the image in pixels.

        Parameters
        ----------
        width : int
            The width of the image in pixels.
        """
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.SUBARRAYHSIZE, width)

    @property
    def height(self):
        """
        The height of the image in pixels.

        This property can be used to get the height of the image in pixels.

        Returns:
        --------
        int:
            The height of the image in pixels.
        """
        return int(self.cam.prop_getvalue(dcam.DCAM_IDPROP.SUBARRAYVSIZE))

    @height.setter
    def height(self, height: int):
        """
        Set the height of the image in pixels.

        This property can be used to set the height of the image in pixels.

        Parameters
        ----------
        height : int
            The height of the image in pixels.
        """
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.SUBARRAYVSIZE, height)

    @property
    def offset_x(self):
        """
        The x offset of the image in pixels.

        This property can be used to get the x offset of the image in pixels.

        Returns:
        --------
        int:
            The x offset of the image in pixels.
        """
        return self.cam.prop_getvalue(dcam.DCAM_IDPROP.SUBARRAYVPOS)

    @offset_x.setter
    def offset_x(self, offset_x: int):
        """
        Set the x offset of the image in pixels.

        This property can be used to set the x offset of the image in pixels.

        Parameters
        ----------
        offset_x : int
            The x offset of the image in pixels.
        """
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.SUBARRAYVPOS, offset_x)

    @property
    def offset_y(self):
        """
        The y offset of the image in pixels.

        This property can be used to get the y offset of the image in pixels.

        Returns:
        --------
        int:
            The y offset of the image in pixels.
        """
        return self.cam.prop_getvalue(dcam.DCAM_IDPROP.SUBARRAYHPOS)

    @offset_y.setter
    def offset_y(self, offset_y: int):
        """
        Set the y offset of the image in pixels.

        This property can be used to set the y offset of the image in pixels.

        Parameters
        ----------
        offset_y : int
            The y offset of the image in pixels.
        """
        self.cam.prop_setvalue(dcam.DCAM_IDPROP.SUBARRAYHPOS, offset_y)


if __name__ == '__main__':
    service = HamamatsuCamera()
    service.run()
