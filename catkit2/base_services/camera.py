from ..testbed.service import Service

import threading
import numpy as np


class StoppedAcquisition:
    '''Context manager for stopping and restarting the acquisition temporarily.
    '''
    def __init__(self, cam):
        self.cam = cam

    def __enter__(self):
        self.was_running = self.cam.is_acquiring.get()[0] > 0

        if self.was_running:
            self.cam.end_acquisition()

            # Wait for the acquisition to actually end.
            while self.cam.is_acquiring.get()[0]:
                self.cam.sleep(0.001)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.was_running:
            self.cam.start_acquisition()


class CameraService(Service):
    NUM_FRAMES_IN_BUFFER = 20
    PIXEL_DTYPE = 'float32'

    def __init__(self, service_type):
        super().__init__(service_type)

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

    def open(self):
        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.log.info('Creating data streams using base camera service')
        
        # Reading properties from the configuration file.
        # This is handled by the base class

        offset_x = self.config.get('offset_x', 0)
        offset_y = self.config.get('offset_y', 0)

        # frame orientation
        self.rot90 = self.config.get('rot90', False)
        self.flip_x = self.config.get('flip_x', False)
        self.flip_y = self.config.get('flip_y', False)

        self.log.info('Camera orientation: rot90={}, flip_x={}, flip_y={}'.format(self.rot90, self.flip_x, self.flip_y))

        self.log.info('Configured sensor width: {}, height: {}'.format(self.sensor_width, self.sensor_height))

        # width and height of the ROI
        self.width = self.config.get('width', self.sensor_width - offset_x) # check if this is what we want 

        self.height = self.config.get('height', self.sensor_height - offset_y)

        self.log.info('Configured ROI width: {}, height: {}'.format(self.width, self.height))

        # self.offset_x and self.offset_y should correspond to what you are actually seeing in the image
        # Note that get_camera_offset must be called before updating the values of self.width and self.height.


        self.gain = self.config.get('gain', 0)
        self.exposure_time = self.config.get('exposure_time', 1000)


        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES_IN_BUFFER)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], self.NUM_FRAMES_IN_BUFFER)

        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES_IN_BUFFER)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))

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

        make_property_helper('width', dtype='int64')
        make_property_helper('height', dtype='int64')
        make_property_helper('offset_x', dtype='int64')
        make_property_helper('offset_y', dtype='int64')

        make_property_helper('exposure_time', dtype='int64')
        make_property_helper('gain', dtype='int64')

        make_property_helper('sensor_width', read_only=True, dtype='int64')
        make_property_helper('sensor_height', read_only=True, dtype='int64')

        make_property_helper('rot90', read_only=True)
        make_property_helper('flip_x', read_only=True)
        make_property_helper('flip_y', read_only=True)

        self.make_command('start_acquisition', self._start_acquisition)
        self.make_command('end_acquisition', self._end_acquisition)

        self.temperature_thread = threading.Thread(target=self.monitor_temperature)
        self.temperature_thread.start()

    def main(self):
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def close(self):
        self.temperature_thread.join()

    def acquisition_loop(self):
        # CHECK: We need to check if the data stream has the right size and datatype after the rotation and flipping for the correct dimensions. 

        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])
        has_correct_parameters &= self.images.dtype == self.PIXEL_DTYPE

        if not has_correct_parameters:
            self.images.update_parameters(self.PIXEL_DTYPE, [self.height, self.width], self.NUM_FRAMES_IN_BUFFER)
            # what does it mean for rot90?

        # Start acquisition on the camera.
        self.start_acquisition()

        # Communicate to outside that we started acquisition.
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))

        try:
            # Wait until we are commanded to stop acquisition.
            while self.should_be_acquiring.is_set() and not self.should_shut_down:
                img = self.capture_image()
                flipped_img = self.rot_flip_image(img)
                self.images.submit_data(flipped_img)

        finally:
            # Communicate with the simulator to stop camera acquisition.
            self.testbed.simulator.end_camera_acquisition(camera_name=self.id)
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))
            
    def get_camera_offset(self, x, y):        
        """Convert relative camera offsets given by the user to absolute offsets in camera array coordinates.

        This is done by performing the following procedure:
        1.) Translate the origin to the center of the ROI.
        2.) if rot90 is True, rotate 90 degrees counter-clockwise about the center of the ROI
        3.) Translate the origin back to the upper left fo the ROI.
        4.) If flip_x is True, reflect in x.
        5.) If flip_y is True, reflect in y.

        Parameters
        ----------
        x: float
            The x-offset coordinate
        y: float
            The y-offset coordinate
        Returns
        -------
        new_x, new_y: float, float
            The transformed x and y coordinates for their location in camera array coordinates. If there is no rotation
            or flip in x or y, then this returns the same x, y values that are input.
        """
        # Define the translation matrix T to get to the center of the ROI.
        T = np.zeros((3, 3))
        np.fill_diagonal(T, 1)
        T[0][-1] = -self.width / 2
        T[1][-1] = -self.height / 2

        # Initialize rotation matrix R.
        R = np.zeros((3, 3))

        # Initialize x reflection matrix, X. Defaults to unity matrix.
        X = np.eye(3, 3)

        # Initialize y reflection matrix, Y. Defaults to unity matrix.
        Y = np.eye(3, 3)

        if self.rot90:
            # Define rotation matrix.
            R[0][1] = -1
            R[1][0] = 1
            R[2][2] = 1
        else:
            # Default to unity matrix.
            np.fill_diagonal(R, 1)

        if self.flip_x:
            # Define x reflection matrix.
            X[0][0] = -1

        if self.flip_y:
            # Define y reflection matrix.
            Y[1][1] = -1

        # Define translation matrix back so that the origin is in the upper left as expected.
        T_back = np.eye(3, 3)

        if self.rot90:
            # Want to come back to new origin for which the height/width dimensions will be flipped if rotated.
            T_back[0][-1] = self.height / 2
            T_back[1][-1] = self.width / 2
        else:
            T_back[0][-1] = self.width / 2
            T_back[1][-1] = self.height / 2

        # Perform the dot product. First flip in x to establish top left origin, then translate to ROI center, rotate,
        # translate back to origin, flip in x, and finally flip in y.
        coords = [x, y, 1]
        new_coords = np.linalg.multi_dot([T_back, Y, X, R, T, coords])

        return new_coords[0], new_coords[1]

    def rot_flip_image(self, img):
        # rotation needs to happen first
        if self.rot90:
            img = np.rot90(img)
        if self.flip_x:
            img = np.flipud(img)
        if self.flip_y:
            img = np.fliplr(img)
        return np.ascontiguousarray(img)  

    def _start_acquisition(self):
        self.should_be_acquiring.set()

    def _end_acquisition(self):
        self.should_be_acquiring.clear()

    @property
    def width(self): # image 
        # TODO: ROI transformation here.
        if self.rot90:
            return self.get_roi_height() # get - sensor space ; get from the camera
        else:
            return self.get_roi_width() 

    # input of the width is in user space
    # width is in user space
    # self.width  --> user space
    # input you send to the set function --> sensor space

    @width.setter
    def width(self, width):
        # TODO: ROI transformation here.
        if self.rot90:
            self.set_roi_height(width) # set - sensor space 
        else:
            self.set_roi_width(width)

    @property
    def height(self):
        # TODO: ROI transformation here.
        if self.rot90:
            return self.get_roi_width()
        else:
            return self.get_roi_height()

    @height.setter
    def height(self, height):
        # TODO: ROI transformation here.
        if self.rot90:
            self.set_roi_width(height)
        else:
            self.set_roi_height(height)

    @property
    def offset_x(self):
        # TODO: ROI transformation here.
        if self.rot90:
            return self.get_roi_offset_y()
        else:
            return self.get_roi_offset_x()

    @offset_x.setter
    def offset_x(self, offset_x, offset_y):
        # inverse transformation to go back to the sensor space when putting this back to the camera --> set_roi_offset_x()
        # TODO: ROI transformation here.
        camera_offset_x, _ = self.get_camera_offset(offset_x, offset_y)
        self.set_roi_offset_x(ofcamera_offset_xset_x)

    @property
    def offset_y(self):
        # TODO: ROI transformation here.
        if self.rot90:
            return self.get_roi_offset_x()
        else:
            return self.get_roi_offset_y()

    @offset_y.setter
    def offset_y(self, offset_x, offset_y):
        # TODO: ROI transformation here.
        _, camera_offset_y = self.get_camera_offset(offset_x, offset_y)
        self.set_roi_offset_y(camera_offset_y)

    @property
    def sensor_width(self):
        # TODO: ROI transformation here.
        if self.rot90:
            return self.get_sensor_height()
        else:
            return self.get_sensor_width()

    @property
    def sensor_height(self):
        # TODO: ROI transformation here.
        if self.rot90:
            return self.get_sensor_width()
        else:
            return self.get_sensor_height()

    def start_acquisition(self):
        '''Start acquisition sequence on the camera.
        '''
        raise NotImplementedError()

    def end_acquisition(self):
        '''End acquisition sequence on the camera.
        '''
        raise NotImplementedError()

    def capture_image(self):
        '''Capture an image on the camera and return it.
        '''
        raise NotImplementedError()

    def get_roi_width(self):
        '''Get the width of the ROI on the camera.
        '''
        raise NotImplementedError()

    def set_roi_width(self, width):
        '''Set the width of the ROI on the camera.
        '''
        raise NotImplementedError()

    def get_roi_height(self):
        '''Get the height of the ROI on the camera.
        '''
        raise NotImplementedError()

    def set_roi_height(self, height):
        '''Set the height of the ROI on the camera.
        '''
        raise NotImplementedError()

    def get_roi_offset_x(self):
        '''Get the x-offset of the ROI on the camera.
        '''
        raise NotImplementedError()

    def set_roi_offset_x(self, offset_x):
        '''Set the x-offset of the ROI on the camera.
        '''
        raise NotImplementedError()

    def get_roi_offset_y(self):
        '''Get the y-offset of the ROI on the camera.
        '''
        raise NotImplementedError()

    def set_roi_offset_y(self):
        '''Set the y-offset of the ROI on the camera.
        '''
        raise NotImplementedError()

    def get_sensor_width(self):
        '''Get the width of the camera sensor.
        '''
        raise NotImplementedError()

    def get_sensor_height(self):
        '''Get the height of the camera sensor.
        '''
        raise NotImplementedError()

    def get_exposure_time(self):
        '''Get the exposure time on the camera.
        '''
        raise NotImplementedError()

    def set_exposure_time(self):
        '''Set the exposure time on the camera.
        '''
        raise NotImplementedError()

    def get_gain(self):
        '''Get the gain on the camera.
        '''
        raise NotImplementedError()

    def set_gain(self):
        '''Set the gain on the camera.
        '''
        raise NotImplementedError()

    def get_temperature(self):
        '''Get the temperature on the camera.
        '''
        raise NotImplementedError()
