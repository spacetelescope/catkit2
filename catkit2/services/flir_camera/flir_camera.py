import threading
import time

from PySpin import PySpin
import numpy as np

from catkit2.testbed.service import Service
from catkit2.testbed.tracing import trace_interval

def _create_property(flir_property_name, read_only=False, stopped_acquisition=True):
    def getter(self):
        with self.mutex:
            return getattr(self.cam, flir_property_name).GetValue()

    if read_only:
        setter = None
    else:
        def setter(self, value):
            was_running = self.is_acquiring.get()[0] > 0

            if was_running and stopped_acquisition:
                self.end_acquisition()

                while self.is_acquiring.get()[0]:
                    time.sleep(0.001)

            with self.mutex:
                getattr(self.cam, flir_property_name).SetValue(value)

            if was_running and stopped_acquisition:
                self.start_acquisition()

    return property(getter, setter)

def _create_enum_property(flir_property_name, enum_name, stopped_acquisition=True):
    def getter(self):
        with self.mutex:
            value = getattr(self.cam, flir_property_name).GetValue()

        # Reverse search in enum dictionary.
        for key, val in getattr(self, enum_name).items():
            if value == val:
                return key

        raise KeyError('Value not recognized.')

    def setter(self, value):
        value = getattr(self, enum_name)[value]

        was_running = self.is_acquiring.get()[0] > 0

        if was_running and stopped_acquisition:
            self.end_acquisition()

            while self.is_acquiring.get()[0]:
                time.sleep(0.001)

        with self.mutex:
            getattr(self.cam, flir_property_name).SetValue(value)

        if was_running and stopped_acquisition:
            self.start_acquisition()

    return property(getter, setter)

class FlirCamera(Service):
    NUM_FRAMES_IN_BUFFER = 20

    pixel_format_enum = {
        'mono8': PySpin.PixelFormat_Mono8,
        'mono12p': PySpin.PixelFormat_Mono12p,
        'mono16': PySpin.PixelFormat_Mono16
    }

    adc_bit_depth_enum = {
        '8bit': PySpin.AdcBitDepth_Bit8,
        '10bit': PySpin.AdcBitDepth_Bit10,
        '12bit': PySpin.AdcBitDepth_Bit12,
        '14bit': PySpin.AdcBitDepth_Bit14
    }

    def __init__(self):
        super().__init__('flir_camera')

        self.serial_number = self.config['serial_number']

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

        # Create lock for camera access
        self.mutex = threading.Lock()

    def open(self):
        self.system = PySpin.System.GetInstance()
        self.cam_list = self.system.GetCameras()
        self.cam = self.cam_list.GetBySerial(str(self.serial_number))

        self.cam.Init()

        # Make sure that the camera is stopped.
        self.cam.BeginAcquisition()
        self.cam.EndAcquisition()

        # Turn off indicator led
        self.cam.DeviceIndicatorMode.SetValue(PySpin.DeviceIndicatorMode_ErrorStatus)

        # Set standard exposure settings
        self.cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        self.cam.ExposureMode.SetValue(PySpin.ExposureMode_Timed)
        self.cam.GainAuto.SetValue(PySpin.GainAuto_Off)
        self.cam.GammaEnable.SetValue(False)
        self.cam.BlackLevelClampingEnable.SetValue(True)
        self.cam.BlackLevel.SetValue(1 / 255 * 100)
        self.cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
        self.cam.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_NewestOnly)

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.images = self.make_data_stream('images', 'float32', [self.sensor_height, self.sensor_width], self.NUM_FRAMES_IN_BUFFER)
        self.temperature = self.make_data_stream('temperature', 'float64', [1], self.NUM_FRAMES_IN_BUFFER)

        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], self.NUM_FRAMES_IN_BUFFER)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))

        # Create properties
        def make_property_helper(name, read_only=False):
            if read_only:
                self.make_property(name, lambda: getattr(self, name))
            else:
                self.make_property(name, lambda: getattr(self, name), lambda val: setattr(self, name, val))

        # Set properties from config.
        self.width = self.config['width']
        self.height = self.config['height']
        self.offset_x = self.config['offset_x']
        self.offset_y = self.config['offset_y']

        self.pixel_format = self.config['pixel_format']
        self.adc_bit_depth = self.config['adc_bit_depth']

        make_property_helper('exposure_time')
        make_property_helper('gain')

        make_property_helper('width')
        make_property_helper('height')
        make_property_helper('offset_x')
        make_property_helper('offset_y')

        make_property_helper('sensor_width', read_only=True)
        make_property_helper('sensor_height', read_only=True)

        make_property_helper('pixel_format')
        make_property_helper('adc_bit_depth')

        make_property_helper('acquisition_frame_rate')
        make_property_helper('acquisition_frame_rate_enable')

        make_property_helper('device_name', read_only=True)

        self.make_command('start_acquisition', self.start_acquisition)
        self.make_command('end_acquisition', self.end_acquisition)

        self.temperature_thread = threading.Thread(target=self.monitor_temperature)
        self.temperature_thread.start()

    def close(self):
        self.temperature_thread.join()

        self.cam.DeInit()
        self.cam = None
        self.cam_list.Clear()

        self.system.ReleaseInstance()
        self.system = None

    def main(self):
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def acquisition_loop(self):
        pixel_dtype = 'float32'

        if self.pixel_format == 'mono8':
            pixel_format = PySpin.PixelFormat_Mono8
        else:
            pixel_format = PySpin.PixelFormat_Mono16

        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])
        has_correct_parameters = has_correct_parameters and (self.images.dtype == pixel_dtype)

        if not has_correct_parameters:
            self.images.update_parameters(pixel_dtype, [self.height, self.width], self.NUM_FRAMES_IN_BUFFER)

        self.cam.BeginAcquisition()
        self.is_acquiring.submit_data(np.array([1], dtype='int8'))

        try:
            while self.should_be_acquiring.is_set() and not self.should_shut_down:
                try:
                    with self.mutex:
                        image_result = self.cam.GetNextImage(10)
                except PySpin.SpinnakerException as e:
                    if e.errorcode == -1011:
                        # The timeout was triggered. Nothing to worry about.
                        continue
                    elif e.errorcode == -1010:
                        # The camera is not streaming anymore.
                        break
                    raise

                with trace_interval('processing frame'):
                    try:
                        if image_result.IsIncomplete():
                            continue

                        img = image_result.Convert(pixel_format).GetNDArray().astype(pixel_dtype, copy=False)

                        # Submit image to datastream.
                        self.images.submit_data(img)

                    finally:
                        image_result.Release()
        finally:
            self.cam.EndAcquisition()
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

    exposure_time = _create_property('ExposureTime', stopped_acquisition=False)
    gain = _create_property('Gain', stopped_acquisition=False)

    width = _create_property('Width')
    height = _create_property('Height')
    offset_x = _create_property('OffsetX', stopped_acquisition=False)
    offset_y = _create_property('OffsetY', stopped_acquisition=False)

    sensor_width = _create_property('SensorWidth', read_only=True)
    sensor_height = _create_property('SensorHeight', read_only=True)

    pixel_format = _create_enum_property('PixelFormat', 'pixel_format_enum')
    adc_bit_depth = _create_enum_property('AdcBitDepth', 'adc_bit_depth_enum')

    acquisition_frame_rate = _create_property('AcquisitionFrameRate', stopped_acquisition=False)
    acquisition_frame_rate_enable = _create_property('AcquisitionFrameRateEnable')

    @property
    def device_name(self):
        with self.mutex:
            return self.cam.TLDevice.DeviceModelName.GetValue()

    def get_temperature(self):
        with self.mutex:
            return self.cam.DeviceTemperature.GetValue()

if __name__ == '__main__':
    service = FlirCamera()
    service.run()
