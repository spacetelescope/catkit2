import threading
from PySpin import PySpin
import numpy as np
from contextlib import nullcontext

from catkit2.base_services import CameraService, StoppedAcquisition


def make_getter(flir_property_name):
    def getter(self):
        with self.mutex:
            return getattr(self.cam, flir_property_name).GetValue()

    return getter


def make_setter(flir_property_name, requires_stopped_acquisition=True):
    def setter(self, value):
        if requires_stopped_acquisition:
            context_manager = StoppedAcquisition(self)
        else:
            context_manager = nullcontext()

        with context_manager:
            with self.mutex:
                getattr(self.cam, flir_property_name).SetValue(value)

    return setter


def make_enum_getter(flir_property_name, enum_values):
    def getter(self):
        with self.mutex:
            value = getattr(self.cam, flir_property_name).GetValue()

        # Reverse search in enum dictionary.
        for key, val in enum_values.items():
            if value == val:
                return key

    return getter


def make_enum_setter(flir_property_name, enum_name, requires_stopped_acquisition=True):
    def setter(self, value):
        value = getattr(self, enum_name)[value]

        if requires_stopped_acquisition:
            context_manager = StoppedAcquisition(self)
        else:
            context_manager = nullcontext()

        with context_manager:
            with self.mutex:
                getattr(self.cam, flir_property_name).SetValue(value)

    return setter


class FlirCamera(CameraService):
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
        super().__init__('flir_camera_v2')

        self.serial_number = self.config['serial_number']

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

        self.pixel_format = self.config['pixel_format']
        self.adc_bit_depth = self.config['adc_bit_depth']

        super().open()

    def close(self):
        super().close()

        self.cam.DeInit()
        self.cam = None
        self.cam_list.Clear()

        self.system.ReleaseInstance()
        self.system = None

    def start_acquisition(self):
        self.cam.BeginAcquisition()

    def end_acquisition(self):
        self.cam.EndAcquisition()

    def capture_image(self):
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
                    return
                raise

            try:
                if image_result.IsIncomplete():
                    continue

                img = image_result.Convert(pixel_format).GetNDArray().astype(pixel_dtype, copy=False)

                # Submit image to datastream.
                self.images.submit_data(img)

            finally:
                image_result.Release()

    get_roi_width = make_getter('Width')
    set_roi_width = make_setter('Width')

    get_roi_height = make_getter('Height')
    set_roi_height = make_setter('Height')

    get_roi_offset_x = make_getter('OffsetX')
    set_roi_offset_x = make_setter('OffsetX', requires_stopped_acquisition=False)

    get_roi_offset_y = make_getter('OffsetY')
    set_roi_offset_y = make_setter('OffsetY', requires_stopped_acquisition=False)

    get_sensor_width = make_getter('SensorWidth')
    get_sensor_height = make_getter('SensorHeight')

    get_exposure_time = make_getter('ExposureTime')
    set_exposure_time = make_setter('ExposureTime', requires_stopped_acquisition=False)

    get_gain = make_getter('Gain')
    set_gain = make_setter('Gain', requires_stopped_acquisition=False)

    get_temperature = make_getter('DeviceTemperature')

    get_pixel_format = make_enum_getter('PixelFormat', pixel_format_enum)
    set_pixel_format = make_enum_setter('PixelFormat', pixel_format_enum)

    get_adc_bit_depth = make_enum_getter('AdcBitDepth', adc_bit_depth_enum)
    set_adc_bit_depth = make_enum_setter('AdcBitDepth', adc_bit_depth_enum)
