import zwoasi

from catkit2.protocol.service import Service, parse_service_args

from threading import Lock
import time

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
    def __init__(self, zwo_camera):
        self.camera = zwo_camera

    def __enter__(self):
        self.was_stopped = self.camera.is_acquiring

        if self.was_stopped:
            self.camera.end_acquisition()

            while self.camera.is_acquiring:
                time.sleep(0.001)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.was_stopped:
            self.start_acquisition()

class ZwoCamera(Service):
    NUM_FRAMES_IN_BUFFER = 20

    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'zwo_camera', testbed_port)

        config = self.configuration

        self.shutdown_flag = False
        self.is_acquiring = False
        self.should_be_acquiring = True

        # Create lock for camera access
        self.mutex = Lock()

        # Attempt to find USB camera.
        num_cameras = zwoasi.get_num_cameras()
        if num_cameras == 0:
            raise RuntimeError("Not a single ZWO camera is connected.")

        # Get camera id and name.
        cameras_found = zwoasi.list_cameras()  # Model names of the connected cameras.
        camera_index = cameras_found.index(config['device_name'])

        # Create a camera object using the zwoasi library.
        self.camera = zwoasi.Camera(camera_index)

        # Get all of the camera controls.
        controls = self.camera.get_controls()

        # Restore all controls to default values, in case any other application modified them.
        for c in controls:
            self.camera.set_control_value(controls[c]['ControlType'], controls[c]['DefaultValue'])

        # Set bandwidth overload control to minvalue.
        self.camera.set_control_value(zwoasi.ASI_BANDWIDTHOVERLOAD, self.camera.get_controls()['BandWidth']['MinValue'])

        try:
            # Force any single exposure to be halted
            self.camera.stop_video_capture()
            self.camera.stop_exposure()
        except Exception:
            # Catch and hide exceptions that get thrown if the camera was already stopped.
            pass

        # Set image format to be RAW16, although camera is only 12-bit.
        self.camera.set_image_type(zwoasi.ASI_IMG_RAW16)

        # Set device values from config file
        self.subarray_x = config['subarray_x']
        self.subarray_y = config['subarray_y']
        self.width = config['width']
        self.height = config['height']

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], NUM_FRAMES_IN_BUFFER)

        # Create properties
        def make_property_helper(name, read_only=False):
            if read_only:
                self.make_property(name, lambda: return getattr(self, name))
            else:
                self.make_property(name, lambda: return getattr(self, name), lambda val: setattr(self, name, val))

        make_property_helper('exposure_time')
        make_property_helper('gain')

        make_property_helper('width')
        make_property_helper('height')
        make_property_helper('offset_x')
        make_property_helper('offset_y')

        make_property_helper('temperature', read_only=True)
        register_property_helper('sensor_width', read_only=True)
        make_property_helper('sensor_height', read_only=True)

        make_property_helper('device_name', read_only=True)
        make_property_helper('is_acquiring', read_only=True)

        self.make_command('start_acquisition', self.start_acquisition)
        self.make_command('end_acquisition', self.end_acquisition)

    def main(self):
        while not self.shutdown_flag:
            if not self.should_be_acquiring:
                time.sleep(0.001)
                continue

            self.acquisition_loop()

    def acquisition_loop(self):
        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])

        if not has_correct_parameters:
            self.images.set_parameters('uint16', [self.height, self.width], self.NUM_FRAMES_IN_BUFFER)

        self.camera.start_video_capture()
        self.is_acquiring = True

        timeout = 10000 # ms

        try:
            while self.should_be_acquiring and not self.shutdown_flag:
                img = self.camera.capture_video_frame(timeout=timeout)

                # Submit frame.
                frame = self.images.request_new_frame()
                frame.data[:] = img
                self.images.submit_frame(frame.id)
        finally:
            self.camera.stop_video_capture()
            self.is_acquiring = False

    def start_acquisition(self):
        self.should_be_acquiring = True

    def end_acquisition(self):
        self.should_be_acquiring = False

    def shutdown(self):
        self.shutdown_flag = True

    @property
    def exposure_time(self):
        exposure_time, auto = self.camera.get_control_value(zwoasi.ASI_EXPOSURE)
        return exposure_time

    @exposure_time.setter
    def exposure_time(self, exposure_time):
        self.camera.set_control_value(zwoasi.ASI_EXPOSURE, int(exposure_time))

    @property
    def gain(self):
        gain, auto = self.camera.get_control_value(zwoasi.ASI_GAIN)
        return gain

    @gain.setter
    def gain(self, gain):
        self.camera.set_control_value(zwoasi.ASI_GAIN, gain)

    @property
    def temperature(self):
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
        roi_format[0] = width
        self.camera.set_roi_format(*roi_format)

    @property
    def height(self):
        width, height, bins, image_type = self.camera.get_roi_format()

        return height

    @width.setter
    def height(self, height):
        roi_format = self.camera.get_roi_format()
        roi_format[1] = height
        self.camera.set_roi_format(*roi_format)

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
