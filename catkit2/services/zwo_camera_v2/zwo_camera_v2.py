import os
import numpy as np
import zwoasi

from catkit2.base_services import CameraService


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


class ZwoCamera(CameraService):
    def __init__(self):
        super().__init__('zwo_camera_v2')

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

        # Get exposure discretization parameters.
        self.exposure_time_step_size = self.config.get('exposure_time_step_size', 1)
        self.exposure_time_offset_correction = self.config.get('exposure_time_offset_correction', 0)
        self.exposure_time_base_step = self.config.get('exposure_time_base_step', 1)
        self.exposure_time = self.config.get('exposure_time', 1000)

        # Set up general camera properties.
        super().open()

    def close(self):
        super().close()

        self.camera.close()

    def start_acquisition(self):
        self.camera.start_video_capture()

    def end_acquisition(self):
        self.camera.stop_video_capture()

    def capture_image(self):
        timeout = 10000  # ms

        img = self.camera.capture_video_frame(timeout=timeout)

        return img.astype('float32')

    def get_roi_width(self):
        width, height, bins, image_type = self.camera.get_roi_format()

        return width

    def set_roi_width(self, width):
        roi_format = self.camera.get_roi_format()
        offset_x, offset_y = self.camera.get_roi_start_position()

        roi_format[0] = width

        self.camera.set_roi_format(*roi_format)
        self.camera.set_roi_start_position(offset_x, offset_y)

    def get_roi_height(self):
        width, height, bins, image_type = self.camera.get_roi_format()

        return height

    def set_roi_height(self, height):
        roi_format = self.camera.get_roi_format()
        offset_x, offset_y = self.camera.get_roi_start_position()

        roi_format[1] = height

        self.camera.set_roi_format(*roi_format)
        self.camera.set_roi_start_position(offset_x, offset_y)

    def get_roi_offset_x(self):
        offset_x, _ = self.camera.get_roi_start_position()

        return offset_x

    def set_roi_offset_x(self, offset_x):
        _, offset_y = self.camera.get_roi_start_position()

        self.camera.set_roi_start_position(offset_x, offset_y)

    def get_roi_offset_y(self):
        _, offset_y = self.camera.get_roi_start_position()

        return offset_y

    def set_roi_offset_y(self, offset_y):
        offset_x, _ = self.camera.get_roi_start_position()

        self.camera.set_roi_start_position(offset_x, offset_y)

    def get_sensor_width(self):
        cam_info = self.camera.get_camera_property()

        return cam_info['MaxWidth']

    def get_sensor_height(self):
        cam_info = self.camera.get_camera_property()

        return cam_info['MaxHeight']

    def get_exposure_time(self):
        exposure_time, auto = self.camera.get_control_value(zwoasi.ASI_EXPOSURE)
        return exposure_time - self.exposure_time_offset_correction

    def set_exposure_time(self, exposure_time):
        exposure_time += self.exposure_time_offset_correction
        exposure_time = np.round((exposure_time - self.exposure_time_base_step) / self.exposure_time_step_size)
        exposure_time = np.maximum(exposure_time, 0)
        exposure_time = exposure_time * self.exposure_time_step_size + self.exposure_time_base_step

        self.camera.set_control_value(zwoasi.ASI_EXPOSURE, int(exposure_time))

    def get_gain(self):
        gain, _ = self.camera.get_control_value(zwoasi.ASI_GAIN)

        return gain

    def set_gain(self, gain):
        self.camera.set_control_value(zwoasi.ASI_GAIN, int(gain))

    def get_temperature(self):
        temperature_times_ten, _ = self.camera.get_control_value(zwoasi.ASI_TEMPERATURE)

        return temperature_times_ten / 10


if __name__ == '__main__':
    service = ZwoCamera()
    service.run()
