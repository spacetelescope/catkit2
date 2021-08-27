from PySpin import PySpin

from hicat2.bindings import Module, DataStream
from hicat2.testbed import parse_module_args

from threading import Lock
import time

def _create_property(flir_property_name, read_only=False, stopped_acquisition=True):
    def getter(self):
        with self.mutex:
            return getattr(self.cam, flir_property_name).GetValue()

    if read_only:
        setter = None
    else:
        def setter(self, value):
            if stopped_acquisition:
                self.end_acquisition()

                while self.is_acquiring:
                    time.sleep(0.001)

            with self.mutex:
                getattr(self.cam, flir_property_name).SetValue(value)

            if stopped_acquisition:
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

        if stopped_acquisition:
            self.end_acquisition()

            while self.is_acquiring:
                time.sleep(0.001)

        with self.mutex:
            getattr(self.cam, flir_property_name).SetValue(value)

        if stopped_acquisition:
            self.start_acquisition()

    return property(getter, setter)

class FlirCameraModule(Module):
    NUM_FRAMES_IN_BUFFER = 20

    def __init__(self):
        args = parse_module_args()
        Module.__init__(self, args.module_name, args.module_port)

        testbed = Testbed(args.testbed_server_port)
        config = testbed.config['modules'][self.name]
        self.serial_number = config['serial_number']

        self.shutdown_flag = False
        self.is_acquiring = False
        self.should_be_acquiring = True

        # Create lock for camera access
        self.mutex = Lock()

        self.system = PySpin.System.GetInstance()
        self.cam_list = self.system.GetCameras()
        self.cam = self.cam_list.GetBySerial(self.serial_number)

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
        self.cam.BlackLevel.SetValue(5 / 255 * 100)
        self.cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
        self.cam.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_NewestOnly)

        # Set properties from config.
        self.width = config['width']
        self.height = config['height']
        self.offset_x = config['offset_x']
        self.offset_y = config['offset_y']

        self.pixel_format = config['pixel_format']
        self.adc_bit_depth = config['adc_bit_depth']

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.images = DataStream.create('images', self.name, 'float32', [self.sensor_height, self.sensor_width], NUM_FRAMES_IN_BUFFER)
        self.register_data_stream(self.images)

        # Create properties
        def register_property_helper(name, read_only=False):
            if read_only:
                self.register_property(Property(name, lambda: return getattr(self, name)))
            else:
                self.register_property(Property(name, lambda: return getattr(self, name), lambda val: setattr(self, name, val)))

        register_property_helper('exposure_time')
        register_property_helper('gain')

        register_property_helper('width')
        register_property_helper('height')
        register_property_helper('offset_x')
        register_property_helper('offset_y')

        register_property_helper('temperature', read_only=True)
        register_property_helper('sensor_width', read_only=True)
        register_property_helper('sensor_height', read_only=True)

        register_property_helper('pixel_format')
        register_property_helper('adc_bit_depth')

        register_property_helper('acquisition_frame_rate')
        register_property_helper('acquisition_frame_rate_enable')

        register_property_helper('device_name', read_only=True)
        register_property_helper('is_acquiring', read_only=True)

        self.register_command(Command('start_acquisition', self.start_acquisition))
        self.register_command(Command('end_acquisition', self.end_acquisition))

    def __del__(self):
        self.system.ReleaseInstance()
        self.system = None

    def main(self):
        while not self.shutdown_flag:
            if not self.should_be_acquiring:
                time.sleep(0.001)
                continue

            self.acquisition_loop()

    def acquisition_loop(self):
        if self.pixel_format == 'mono8':
            pixel_format = self.instrument_lib.PixelFormat_Mono8
            pixel_dtype = 'uint8'
        else:
            pixel_format = self.instrument_lib.PixelFormat_Mono16
            pixel_dtype = 'uint16'

        # Make sure the data stream has the right size and datatype.
        has_correct_parameters = np.allclose(self.images.shape, [self.height, self.width])
        has_correct_parameters = has_correct_parameters and (self.images.dtype == pixel_dtype)

        if not has_correct_parameters:
            self.images.set_parameters(pixel_dtype, [self.height, self.width], self.NUM_FRAMES_IN_BUFFER)

        self.cam.BeginAcquisition()
        self.is_acquiring = True

        while self.should_be_acquiring and not self.shutdown_flag:
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

            if image_result.IsIncomplete():
                continue

            img = image_result.Convert(pixel_format).GetData().astype(pixel_dtype)
            img = img.reshape((image_result.GetHeight(), image_result.GetWidth()))

            # Submit image to datastream.
            frame = self.images.request_new_frame()
            frame.data[:] = img
            self.images.submit_frame(frame.id)

            image_result.Release()

        self.cam.EndAcquisition()
        self.is_acquiring = False

    def start_acquisition(self):
        self.should_be_acquiring = True

    def end_acquisition(self):
        self.should_be_acquiring = False

    def shutdown(self):
        self.shutdown_flag = True

    exposure_time = _create_property('ExposureTime', stopped_acquisition=False)
    gain = _create_property('Gain', stopped_acquisition=False)

    width = _create_property('Width')
    height = _create_property('Height')
    offset_x = _create_property('OffsetX', stopped_acquisition=False)
    offset_y = _create_property('OffsetY', stopped_acquisition=False)

    temperature = _create_property('DeviceTemperature', read_only=True)
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
