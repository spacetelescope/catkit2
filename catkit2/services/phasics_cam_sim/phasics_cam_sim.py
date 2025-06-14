import numpy as np
from catkit2.testbed.service import Service
import threading
from time import sleep

class IllegalArgumentError(ValueError):
    pass

class PhasicsCamSim(Service):
    """
    A simulated service class for the Phasics camera.

    This class simulates a camera service with functionality for taking measurements,
    starting and stopping live acquisitions, and managing an image buffer.

    """
    def __init__(self):
        """
        Initializes the PhasicsCamSim object.

        Sets up the simulation parameters, including exposure time, image dimensions,
        and frame buffer size. Also initializes data streams and registers commands.

        Attributes
        ----------
        exposure_time : int
            The default exposure time in milliseconds.
        image_height : int
            The height of the images in pixels.
        image_width : int
            The width of the images in pixels.
        num_frames_in_buffer : int
            The number of frames to maintain in the data buffer.
        images : catkit2.testbed.service.DataStream
            A data stream to manage simulated phase map frames.
        intensity : catkit2.testbed.service.DataStream
            A data stream to manage simulated intensity frames.
        """
        super().__init__('phasics_cam_sim')

        self.exposure_time = self.config.get('exposure_time', 504)
        self.num_frames_in_buffer = self.config.get('buffer_frames', 32)
        self.zernike_polyorder = self.config.get('zernike_poly_order', 9)
        # since the real service will determine width/height based on an image we can hardcode for the simulated version
        self.image_height = 200
        self.image_width = 200
        self.num_frames_in_bufffer = self.config.get('buffer_frames', 32)
        self.framecounter = 0

        # Create data streams.
        # in order to re-use the camera interface I must have something called 'images' which will be an alias for the phase map
        self.images = self.make_data_stream('images', 'float32', [self.image_height, self.image_width], self.num_frames_in_bufffer)
        self.intensity = self.make_data_stream('intensity', 'float32', [self.image_height, self.image_width], self.num_frames_in_bufffer)
        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.num_frames_in_bufffer)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))
        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.clear()

        self.make_command('take_measurement', self.take_measurement)
        self.make_command('start_acquisition', self.start_acquisition)
        self.make_command('end_acquisition', self.end_acquisition)
        self.make_command('phase_filtering', self.phase_filtering)
        self.make_command('phase_projection', self.phase_projection)

        # set the configured exposure time
        self.set_exposure_time(self.exposure_time)
        self.log.info('finished initializing phasics cam service')

    def set_exposure_time(self, exposure_time):
        """
        Sets the camera's exposure time in ms

        Parameters
        ----------
        exposure_time : int
            The exposure time in milliseconds.

        Returns
        -------
        bool
            True if the exposure time is successfully set.
        """
        self.exposure_time = exposure_time
        return True


    def take_measurement(self, num_images=1):
        """
        Takes one or more simulated camera measurements.

        If more than one image is requested, a random phase cube is generated,
        averaged, and returned. Otherwise, a single phase map is generated and returned.

        Parameters
        ----------
        num_images : int, optional
            The number of exposures to average. The default is 1.

        Returns
        -------
        numpy.ndarray
            The simulated phase map (single or averaged) of dimensions (image_height, image_width).
        """
        tlseep = .1
        if num_images > 1:
            for i in range(num_images):
                if i == 0:
                    phase_cube = np.random.rand(self.image_height, self.image_width)
                else:
                    phase_map_temp = np.random.rand(self.image_height, self.image_width)
                    phase_cube = np.dstack((phase_cube, phase_map_temp))

            phase_map = np.mean(phase_cube, axis=2)
            phase_map = phase_cube
            sleep(tlseep)

        else:
            phase_map = np.random.rand(self.image_height, self.image_width)
            sleep(tlseep)

        return phase_map

    def phase_projection(self, phase=None):
        """
        Parameters
        ----------
        phase : numpy.ndarray, optional
            The phase map (single or averaged) of dimensions (image_height, image_width).
        Returns
        -------
        1D numpy array
            The zernike phase projection coefficients
        """
        if phase is None:
            phase = self.take_measurement()
        return 55 * [1]

    def phase_filtering(self, phase=None, projection_coefficient=None, index_list=None, residual=None):
        """
        Parameters
        ----------
        phase : numpy.ndarray
            The phase map (single or averaged) of dimensions (image_height, image_width).
        phase_projection_coefficient :  (1D numpy array)
            Zernike projection coefficient
        index_list : (1D numpy array)
            List of the projection coefficient index to filter
        residual : bool
            If True the residual is return, if False the filtered phase is returned

        Returns
        -------
        numpy.ndarray
            2D Filtered phase map.
        """
        if phase is None:
            raise IllegalArgumentError('phase required arg1')

        if projection_coefficient is None:
            raise IllegalArgumentError('projection_coefficient required arg2')

        if index_list is None:
            raise IllegalArgumentError('index_list required arg3')

        if residual is None:
            raise IllegalArgumentError('residual required arg4')
        # its ok this is fake data anyway
        return self.take_measurement()

    def close(self):
        """
        Closes the service.

        This method is a placeholder for any cleanup actions that might
        be required when shutting down the service.
        """
        return

    def main(self):
        """
        Main loop to manage data acquisition and processing.
        """
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def acquisition_loop(self):
        """
        Handle continuous data acquisition while the service is running.
        """
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))
        sleep(0.1)
        try:
            while self.should_be_acquiring.is_set() and not self.should_shut_down:
                phase_map = np.random.rand(self.image_height, self.image_width)
                intensity = np.random.rand(self.image_height, self.image_width)

                has_correct_parameters = np.allclose(self.images.shape, phase_map.shape)

                if not has_correct_parameters:
                    self.images.update_parameters('float32', phase_map.shape, self.num_frames_in_bufffer)
                self.images.submit_data(phase_map.astype('float32'))

                has_correct_parameters = np.allclose(self.intensity.shape, intensity.shape)

                if not has_correct_parameters:
                    self.intensity.update_parameters('float32', intensity.shape, self.num_frames_in_bufffer)
                self.intensity.submit_data(intensity.astype('float32'))

        finally:
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))

    def start_acquisition(self):
        """
        Start the data acquisition process.
        """
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))
        self.should_be_acquiring.set()

    def end_acquisition(self):
        """
        End the data acquisition process.
        """
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))
        self.should_be_acquiring.clear()

if __name__ == '__main__':
    service = PhasicsCamSim()
    service.run()
