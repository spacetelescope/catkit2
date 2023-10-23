import threading
import time
import os
import numpy as np

from catkit2.testbed.service import Service

import zwoasi

try:
    __ZWO_ASI_LIB = 'ZWO_ASI_LIB'
    __env_filename = os.getenv(__ZWO_ASI_LIB)

    if not __env_filename:
        raise OSError(f"Environment variable '{__ZWO_ASI_LIB}' doesn't exist. Create and point to ASICamera2 lib")

    if not os.path.exists(__env_filename):
        raise OSError(f"File not found: '{__ZWO_ASI_LIB}' -> '{__env_filename}'")

    zwoasi.init(__env_filename)
except Exception as error:
    raise ImportError(f"Failed to load {__ZWO_ASI_LIB} library backend to {zwoasi.__qualname__}") from error

class StoppedAcquisition:
    '''Context manager for stopping and restarting the acquisition temporarily.
    '''
    def __init__(self, zwo_camera):
        self.camera = zwo_camera

    def __enter__(self):
        self.was_running = self.camera.is_acquiring.get()[0] > 0

        if self.was_running:
            self.camera.end_acquisition()

            # Wait for the acquisition to actually end.
            while self.camera.is_acquiring.get()[0]:
                time.sleep(0.001)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.was_running:
            self.camera.start_acquisition()

class ZwoCamera(Service):
    NUM_FRAMES_IN_BUFFER = 20

    def __init__(self):
        super().__init__('zwo_camera')

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

        # Create lock for camera access
        self.mutex = threading.Lock()

    def open(self):
        # Attempt to find USB camera.
        num_cameras = zwoasi.get_num_cameras()
        if num_cameras == 0:
            raise RuntimeError("Not a single ZWO camera is connected.")

        expected_device_name = self.config['device_name']
        expected_device_id = self.config.get('device_id', None)

        for i in range(num_cameras):
            device_name = zwoasi._get_camera_property(i)['Name']

            if not device_name.startswith(expected_device_name):
                continue

            if expected_device_id is None:
                camera_index = i
                break
            else:
                zwoasi._open_camera(i)
                try:
                    device_id = zwoasi._get_id(i)
                    if device_id == str(expected_device_id):
                        camera_index = i
                        break
                except Exception as e:
                    raise RuntimeError(f'Impossible to read camera id for camera {expected_device_name}. It probably doesn\'t support an id.') from e
                finally:
                    zwoasi._close_camera(i)

        else:
            raise RuntimeError(f'Camera {expected_device_name} with id {expected_device_id} not found.')

        # Create a camera object using the zwoasi library.
        self.camera = zwoasi.Camera(camera_index)

        # Get all of the camera controls.
        controls = self.camera.get_controls()

        # Restore all controls to default values, in case any other application modified them.
        for c in controls:
            self.camera.set_control_value(controls[c]['ControlType'], controls[c]['DefaultValue'])

        print('Bandwidth defaults', self.camera.get_controls()['BandWidth'])

        print('Bandwidth before:', self.camera.get_control_value(zwoasi.ASI_BANDWIDTHOVERLOAD))

        # Set bandwidth overload control to minvalue.
        self.camera.set_control_value(zwoasi.ASI_BANDWIDTHOVERLOAD, self.camera.get_controls()['BandWidth']['MaxValue'])

        print('Bandwidth after:', self.camera.get_control_value(zwoasi.ASI_BANDWIDTHOVERLOAD))

        try:
            # Force any single exposure to be halted
            self.camera.stop_video_capture()
            self.camera.stop_exposure()
        except Exception:
            # Catch and hide exceptions that get thrown if the camera was already stopped.
            pass

        # Set image format to be RAW16, although camera is only 12-bit.
        self.camera.set_image_type(zwoasi.ASI_IMG_RAW16)

        # Set device values from config file (set width and height before offsets)
        offset_x = self.config.get('offset_x', 0)
        offset_y = self.config.get('offset_y', 0)
        rot90 = self.config.get('rot90', False)
        flip_x = self.config.get('flip_x', False)
        flip_y = self.config.get('flip_y', False)

        self.width = self.config.get('width', self.sensor_width - offset_x)
        self.height = self.config.get('height', self.sensor_height - offset_y)

        offset_x, offset_y = self.get_camera_offset(offset_x, offset_y)

        self.offset_x = offset_x
        self.offset_y = offset_y
        self.rot90 = rot90
        self.flip_x = flip_x
        self.flip_y = flip_y

        self.gain = self.config.get('gain', 0)
        self.exposure_time_step_size = self.config.get('exposure_time_step_size', 1)
        self.exposure_time_offset_correction = self.config.get('exposure_time_offset_correction', 0)
        self.exposure_time_base_step = self.config.get('exposure_time_base_step', 1)
        self.exposure_time = self.config.get('exposure_time', 1000)

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        # If the sensor is rotated by 90 degrees, make sure to flip the axes in the datastream
        if self.rot90:
            self.images = self.make_data_stream('images', 'float32', [self.sensor_width, self.sensor_height],
                                                self.NUM_FRAMES_IN_BUFFER)
        else:
            self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width],
                                                self.NUM_FRAMES_IN_BUFFER)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], self.NUM_FRAMES_IN_BUFFER)

        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES_IN_BUFFER)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))

        # Create properties
        def make_property_helper(name, read_only=False, requires_stopped_acquisition=False):
            if read_only:
                self.make_property(name, lambda: getattr(self, name))
            else:
                if requires_stopped_acquisition:
                    def setter(val):
                        with StoppedAcquisition(self):
                            setattr(self, name, val)
                else:
                    def setter(val):
                        setattr(self, name, val)

                self.make_property(name, lambda: getattr(self, name), setter)

        make_property_helper('exposure_time')
        make_property_helper('gain')
        make_property_helper('brightness')

        make_property_helper('width', requires_stopped_acquisition=True)
        make_property_helper('height', requires_stopped_acquisition=True)
        make_property_helper('offset_x')
        make_property_helper('offset_y')
        make_property_helper('rot90', read_only=True)
        make_property_helper('flip_x', read_only=True)
        make_property_helper('flip_y', read_only=True)

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
        self.temperature_thread.join()

        self.camera.close()

    def acquisition_loop(self):
        # Make sure the data stream has the right size and datatype.
        if self.rot90:
            has_correct_parameters = np.allclose(self.images.shape, [self.width, self.height])
        else:
            has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])

        if not has_correct_parameters:
            if self.rot90:
                self.images.update_parameters('float32', [self.width, self.height], self.NUM_FRAMES_IN_BUFFER)
            else:
                self.images.update_parameters('float32', [self.height, self.width], self.NUM_FRAMES_IN_BUFFER)

        # Start acquisition.
        self.camera.start_video_capture()
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))

        timeout = 10000  # ms

        try:
            while self.should_be_acquiring.is_set() and not self.should_shut_down:
                img = self.camera.capture_video_frame(timeout=timeout)
                # make sure image has proper rotation and flips for the camera
                img = self.rot_flip_image(img)
                self.images.submit_data(img.astype('float32'))
        finally:
            # Stop acquisition.
            self.camera.stop_video_capture()
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))

    def monitor_temperature(self):
        while not self.should_shut_down:
            temperature = self.get_temperature()
            self.temperature.submit_data(np.array([temperature]))

            self.sleep(1)

    def start_acquisition(self):
        self.should_be_acquiring.set()

    def end_acquisition(self):
        self.should_be_acquiring.clear()

    @property
    def exposure_time(self):
        exposure_time, auto = self.camera.get_control_value(zwoasi.ASI_EXPOSURE)
        return exposure_time - self.exposure_time_offset_correction

    @exposure_time.setter
    def exposure_time(self, exposure_time):
        exposure_time += self.exposure_time_offset_correction
        exposure_time = np.round((exposure_time - self.exposure_time_base_step) / self.exposure_time_step_size)
        exposure_time = np.maximum(exposure_time, 0)
        exposure_time = exposure_time * self.exposure_time_step_size + self.exposure_time_base_step

        self.camera.set_control_value(zwoasi.ASI_EXPOSURE, int(exposure_time))

    @property
    def gain(self):
        gain, auto = self.camera.get_control_value(zwoasi.ASI_GAIN)
        return gain

    @gain.setter
    def gain(self, gain):
        self.camera.set_control_value(zwoasi.ASI_GAIN, int(gain))

    @property
    def brightness(self):
        brightness, auto = self.camera.get_control_value(zwoasi.ASI_BRIGHTNESS)
        return brightness

    @brightness.setter
    def brightness(self, brightness):
        self.camera.set_control_value(zwoasi.ASI_BRIGHTNESS, int(brightness))

    def get_temperature(self):
        temperature_times_ten, auto = self.camera.get_control_value(zwoasi.ASI_TEMPERATURE)
        return temperature_times_ten / 10

    @property
    def sensor_width(self):
        cam_info = self.camera.get_camera_property()

        return cam_info['MaxWidth']

    @property
    def sensor_height(self):
        cam_info = self.camera.get_camera_property()

        return cam_info['MaxHeight']

    @property
    def width(self):
        width, height, bins, image_type = self.camera.get_roi_format()

        return width

    @width.setter
    def width(self, width):
        roi_format = self.camera.get_roi_format()
        offset_x, offset_y = self.camera.get_roi_start_position()
        roi_format[0] = width
        self.camera.set_roi_format(*roi_format)
        self.camera.set_roi_start_position(offset_x, offset_y)

    @property
    def height(self):
        width, height, bins, image_type = self.camera.get_roi_format()

        return height

    @height.setter
    def height(self, height):
        roi_format = self.camera.get_roi_format()
        offset_x, offset_y = self.camera.get_roi_start_position()
        roi_format[1] = height
        self.camera.set_roi_format(*roi_format)
        self.camera.set_roi_start_position(offset_x, offset_y)

    @property
    def offset_x(self):
        offset_x, offset_y = self.camera.get_roi_start_position()

        return offset_x

    @offset_x.setter
    def offset_x(self, offset_x):
        self.camera.set_roi_start_position(offset_x, self.offset_y)

    @property
    def offset_y(self):
        offset_x, offset_y = self.camera.get_roi_start_position()

        return offset_y

    @offset_y.setter
    def offset_y(self, offset_y):
        self.camera.set_roi_start_position(self.offset_x, offset_y)

    def rot_flip_image(self, img):
        # rotation needs to happen first
        if self.rot90:
            img = np.rot90(img)
        if self.flip_x:
            img = np.flipud(img)
        if self.flip_y:
            img = np.fliplr(img)
        return np.ascontiguousarray(img)

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
        T[0][-1] = self.width / 2
        T[1][-1] = -self.height / 2  # Negative due to origin in upper left.

        # Initialize rotation matrix R.
        R = np.zeros((3, 3))

        # Initialize x reflection matrix, X. Defaults to unity matrix.
        X = np.zeros((3, 3))
        np.fill_diagonal(X, 1)

        # Initialize y reflection matrix, Y. Defaults to unity matrix.
        Y = np.zeros((3, 3))
        np.fill_diagonal(Y, 1)

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
            X[1][1] = -1

        if self.flip_y:
            # Define y reflection matrix.
            Y[0][0] = -1

        # Define translation matrix back so that the origin is in the upper left as expected.
        T_back = np.zeros((3, 3))
        np.fill_diagonal(T_back, 1)
        T_back[0][-1] = -self.width / 2
        T_back[1][-1] = self.height / 2

        # Perform the dot product. First flip in x to establish top left origin, then translate to ROI center, rotate,
        # translate back to origin, flip in x, and finally flip in y.
        coords = [x, y, 1]
        new_coords = np.linalg.multi_dot([Y, X, T_back, R, T, coords])

        return new_coords[0], new_coords[1]


if __name__ == '__main__':
    service = ZwoCamera()
    service.run()
