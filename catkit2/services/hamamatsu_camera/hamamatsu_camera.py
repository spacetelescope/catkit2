"""
This module contains a service for Hamamatsu digital cameras.

This service is a wrapper around the DCAM-SDK4.
It provides a simple interface to control the camera and acquire images.
"""
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

    Methods
    -------
    open()
        Open the service.
    main()
        The main function of the service.
    close()
        Close the service.
    acquisition_loop()
        The main acquisition loop.
    monitor_temperature()
        Monitor the temperature of the camera.
    start_acquisition()
        Start the acquisition loop.
    end_acquisition()
        End the acquisition loop.
    get_temperature()
        Get the temperature of the camera.
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
            "Mono8": DCAM_PIXELTYPE.Mono8,
            "Mono16": DCAM_PIXELTYPE.Mono16,
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
        """
        dcam.Dcamapi.init()

        camera_id = self.config.get('camera_id', 0)
        self.cam = dcam.Dcam(camera_id)
        self.log.info('Using camera with ID %s', camera_id)
        self.cam.dev_open()

        self.current_pixel_format = self.config.get('pixel_format', 'Mono16')
        if self.current_pixel_format not in self.pixel_formats:
            raise ValueError('Invalid pixel format: ' +
                             self.current_pixel_format +
                             ', must be one of ' +
                             str(list(self.pixel_formats.keys())))
        self.log.info('Using pixel format: %s', self.current_pixel_format)
        # self.cam.set_pixel_format(self.pixel_formats[self.current_pixel_format])   # TODO

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
        """
        The main function of the service.

        This function is called when the service is started.
        It starts the acquisition loop and waits for incoming frames.
        """
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def close(self):
        """
        Close the service.

        This function is called when the service is closed.
        It stops the acquisition loop and cleans up the camera and data streams.
        """
        self.cam.dev_close()
        self.cam = None


if __name__ == '__main__':
    service = HamamatsuCamera()
    service.run()
