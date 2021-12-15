import threading
import time
import os
import numpy as np

from catkit2.protocol.service import Service, parse_service_args

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

    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'zwo_camera', testbed_port)

        self.shutdown_flag = threading.Event()
        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

        # Create lock for camera access
        self.mutex = threading.Lock()

    def open(self):
        config = self.configuration

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
        self.subarray_x = config.get('subarray_x', 0)
        self.subarray_y = config.get('subarray_y', 0)
        self.width = config.get('width', self.sensor_width - self.subarray_x)
        self.height = config.get('height', self.sensor_height - self.subarray_y)

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES_IN_BUFFER)
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

        make_property_helper('width', requires_stopped_acquisition=True)
        make_property_helper('height', requires_stopped_acquisition=True)
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
        while not self.shutdown_flag.is_set():
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def close(self):
        self.shutdown_flag.set()
        self.temperature_thread.join()

        self.camera.close()

    def acquisition_loop(self):
        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])

        if not has_correct_parameters:
            self.images.update_parameters('float32', [self.height, self.width], self.NUM_FRAMES_IN_BUFFER)

        # Start acquisition.
        self.camera.start_video_capture()
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))

        timeout = 10000 # ms

        try:
            while self.should_be_acquiring.is_set() and not self.shutdown_flag.is_set():
                img = self.camera.capture_video_frame(timeout=timeout)

                self.images.submit_data(img.astype('float32'))
        finally:
            # Stop acquisition.
            self.camera.stop_video_capture()
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))

    def monitor_temperature(self):
        while not self.shutdown_flag.is_set():
            temperature = self.get_temperature()
            self.temperature.submit_data(np.array([temperature]))

            self.shutdown_flag.wait(1)

    def start_acquisition(self):
        self.should_be_acquiring.set()

    def end_acquisition(self):
        self.should_be_acquiring.clear()

    def shut_down(self):
        self.shutdown_flag.set()

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

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = ZwoCamera(service_name, testbed_port)
    service.run()
