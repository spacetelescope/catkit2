from ctypes import c_byte, c_char, c_ulong, c_int, c_short, c_ushort, c_double
from ctypes import cdll, CDLL, Structure, byref, create_string_buffer

import os
import sys

import numpy as np

from catkit2.testbed.service import Service


class TLI_HardwareInformation(Structure):
    _fields_ = [
        ('serialNumber', c_ulong),
        ('modelNumber', c_char * 8),
        ('type', c_ushort),
        ('firmwareVersion', c_ulong),
        ('notes', c_char * 48),
        ('deviceDependantData', c_byte * 12),
        ('hardwareVersion', c_ushort),
        ('modificationState', c_ushort),
        ('numChannels', c_short),
    ]


class ThorlabsCubeMotorKinesis(Service):
    """
    Service for controlling a Thorlabs cube motor.
    """

    def __init__(self):
        super().__init__('thorlabs_cube_motor_kinesis')

        self.cube_model = self.config['cube_model']
        self.stage_model = self.config['stage_model']
        self.motor_type = 0
        self.serial_number = str(self.config['serial_number']).encode("UTF-8")

        # Load the Thorlabs DLLs.
        default_dll_path = r"C:\Program Files\Thorlabs\Kinesis"
        if sys.version_info < (3, 8):
            os.chdir(default_dll_path)
        else:
            os.add_dll_directory(default_dll_path)

        if self.cube_model == 'KDC101':
            dll_name = r"\Thorlabs.MotionControl.KCube.DCServo.dll"
            self.motor_type = 27
        elif self.cube_model == 'TDC001':
            dll_name = r"\Thorlabs.MotionControl.TCube.DCServo.dll"
            self.motor_type = 83
        else:
            raise ValueError(f"Motor type {self.motor_type} not supported.")

        self.lib: CDLL = cdll.LoadLibrary(default_dll_path + dll_name)

        self.unit = None
        self.unit_type = 0
        self.min_position_device = None
        self.max_position_device = None
        self.min_position_config = None
        self.max_position_config = None

    def open(self):
        """
        Open connection to the motor.

        This will also check if the configured characteristics are matching the one the cube has.
        """
        # Build the device list and verify that the device is connected.
        if self.lib.TLI_BuildDeviceList() == 0:
            serial_number_list_size = 35  # 4 * 8 (SN size) + 3 for the commas between the serial numbers
            serial_number_list = create_string_buffer(serial_number_list_size)
            self.lib.TLI_GetDeviceListByTypeExt(serial_number_list, serial_number_list_size, self.motor_type)
            if serial_number_list not in self.serial_number:
                raise ValueError(f"Device with serial number {self.serial_number} not found.")

        # Open the device
        self.lib.CC_Open(self.serial_number)
        self.lib.CC_StartPolling(self.serial_number, c_int(200))

        if self.stage_model == 'MTS50-Z8':
            # Set up the device to convert real units to device units
            steps_per_rev = c_double(512)  # for the MTS50-Z8
            gear_box_ratio = c_double(67.49)  # gearbox ratio
            pitch_mm = c_double(1.0)
        else:
            raise ValueError(f"Stage model {self.stage_model} not supported.")

        # Apply these values to the device
        self.lib.CC_SetMotorParamsExt(self.serial_number, steps_per_rev, gear_box_ratio, pitch_mm)

        # Retrieve the min, max, unit and model from the connected device.
        real_unit = c_double()
        self.lib.CC_GetRealValueFromDeviceUnit(self.serial_number,
                                               self.lib.CC_GetStageAxisMinPos(self.serial_number),
                                               byref(real_unit), 0)
        self.min_position_device = real_unit.value
        self.lib.CC_GetRealValueFromDeviceUnit(self.serial_number,
                                               self.lib.CC_GetStageAxisMaxPos(self.serial_number),
                                               byref(real_unit), 0)
        self.max_position_device = real_unit.value

        # Get the unit of the motor (mm or deg).
        self.unit_type = self.lib.CC_GetMotorTravelMode(self.serial_number)
        if self.unit_type == 1:
            self.unit = 'mm'
        elif self.unit_type == 2:
            self.unit = 'deg'

        # Read min, max, unit and model from service configuration.
        self.min_position_config = self.config['min_position']
        self.max_position_config = self.config['max_position']
        unit_config = self.config['unit']

        firmware_version = c_ulong()
        hardware_version = c_ushort()
        modification_state = c_ushort()
        typ = c_ushort()
        num_channels = c_ushort()
        model_size = TLI_HardwareInformation.modelNumber.size
        model = create_string_buffer(model_size)
        notes_size = TLI_HardwareInformation.notes.size
        notes = create_string_buffer(notes_size)

        self.lib.CC_GetHardwareInfo(self.serial_number, model, model_size, byref(typ), byref(num_channels),
                         notes, notes_size, byref(firmware_version), byref(hardware_version),
                         byref(modification_state))

        # Compare the device parameters to the service configuration.
        if not (self.min_position_device >= self.min_position_config and
                self.max_position_device <= self.max_position_config and
                self.cube_model == model.decode() and
                self.unit == unit_config):
            raise ValueError("Device parameters don't match configuration parameters.")

        self.command = self.make_data_stream('command', 'float64', [1], 20)
        self.current_position = self.make_data_stream('current_position', 'float64', [1], 20)
        # Submit motor starting position to current_position data stream
        self.get_current_position()

        self.make_command('home', self.home)
        self.make_command('stop', self.stop)
        self.make_command('is_in_motion', self.is_in_motion)

    def main(self):
        while not self.should_shut_down:
            try:
                # Get an update for the motor position.
                frame = self.command.get_next_frame(10)
                # Set the current position if a new command has arrived.
                self.set_current_position(frame.data[0])
            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def close(self):
        self.lib.CC_ClearMessageQueue(self.serial_number)
        self.lib.CC_StopPolling(self.serial_number)
        # Close the device
        self.lib.CC_Close(self.serial_number)

    def set_current_position(self, position):
        """
        Set the motor's current position.

        The unit is given in real-life units (mm if translation, deg if rotation).
        """
        if self.min_position_config <= position <= self.max_position_config:
            new_pos_real = c_double(position)  # in real units
            new_pos_dev = c_int()
            self.lib.CC_GetDeviceUnitFromRealValue(self.serial_number,
                                            new_pos_real,
                                            byref(new_pos_dev),
                                            0)
            self.lib.CC_MoveToPosition(self.serial_number, new_pos_dev)
        else:
            self.log.warning(f'Motor not moving since commanded position is outside of configured range.')
            self.log.warning(f'Position limits: {self.min_position_config} {self.unit} <= position <= {self.max_position_config} {self.unit}.')

        # Update the current position data stream.
        self.get_current_position()

    def get_current_position(self):
        current_position = self.lib.CC_GetPosition(self.serial_number)
        real_unit = c_double()
        self.lib.CC_GetRealValueFromDeviceUnit(self.serial_number, current_position, byref(real_unit), 0)
        self.current_position.submit_data(np.array([real_unit.value], dtype='float64'))

    def home(self):
        """
        Home the motor.

        This will block until the motor has finished homing.
        """
        # Home device
        self.lib.CC_ClearMessageQueue(self.serial_number)
        self.lib.CC_Home(self.serial_number)
        self.log.info("Device %s homing\r\n", self.serial_number)

        # wait for completion
        message_type = c_ushort()
        message_id = c_ushort()
        message_data = c_ulong()
        while message_id.value != 0 or message_type.value != 2:
            self.lib.CC_WaitForMessage(self.serial_number, byref(message_type), byref(message_id), byref(message_data))
            self.log.info(message_id, message_type)

        self.log.info("Homed - motor %s", self.serial_number)
        self.lib.CC_ClearMessageQueue(self.serial_number)

        # Update the current position data stream.
        self.get_current_position()

    def stop(self):
        """Stop any current movement of the motor."""
        self.lib.CC_ClearMessageQueue(self.serial_number)
        self.lib.CC_StopProfiled(self.serial_number)

        while self.is_in_motion:
            self.sleep(0.1)
        # Update the current position data stream.
        self.get_current_position()

    def is_in_motion(self):
        """Check if the motor is currently moving."""
        # TODO return self.motor.is_in_motion, return False always for now
        return False


if __name__ == '__main__':
    service = ThorlabsCubeMotorKinesis()
    service.run()
