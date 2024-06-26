"""
The library calls for the Thorlabs cube motor in this script make use and adapt code from
https://github.com/Thorlabs/Motion_Control_Examples/tree/main/Python, which is licensed under the MIT License.
Their original copyright notice and permission notice are included below.

Copyright (c) 2021 Thorlabs

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import os
import sys
import threading

from ctypes import c_ulong, c_int, c_ushort, c_double
from ctypes import cdll, CDLL, byref, create_string_buffer
import numpy as np

from catkit2.testbed.service import Service


default_dll_path = os.environ.get('THORLABS_KINESIS_DLL_PATH')
if default_dll_path is not None:
    if sys.version_info < (3, 8):
        os.chdir(default_dll_path)
    else:
        os.add_dll_directory(default_dll_path)
else:
    raise ValueError('To use Thorlabs cube motors with Kinesis, you need to set the THORLABS_KINESIS_DLL_PATH environment variable.')


class ThorlabsCubeMotorKinesis(Service):
    """
    Service for controlling a Thorlabs cube motor.
    """

    def __init__(self):
        super().__init__('thorlabs_cube_motor_kinesis')

        self.cube_model = self.config['cube_model']
        self.stage_model = self.config['stage_model']
        self.motor_positions = self.config['positions']
        self.motor_type = 0
        self.serial_number = str(self.config['serial_number']).encode("UTF-8")
        self.update_interval = self.config['update_interval']

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

        self.command = None
        self.current_position = None

    def open(self):
        """
        Open connection to the motor.

        This will also check if the configured characteristics are matching the one the cube has.
        """
        # Build the device list and verify that the requested device is connected.
        if self.lib.TLI_BuildDeviceList() == 0:
            # The serial_number_list_size is the size of a list that holds the cubes' serial numbers of one motor type.
            # This allocates a number of Bytes to store the serial numbers.
            # Number of motors * 8 (size in bytes of one serial number) + Number of motors * 1 (bytes for commas between all serial numbers)
            serial_number_list_size = 1024    # can hold more than 100 motor serial numbers, as 100 * (8 + 1) = 900
            serial_number_list = create_string_buffer(serial_number_list_size)
            self.lib.TLI_GetDeviceListByTypeExt(serial_number_list, serial_number_list_size, self.motor_type)
            self.log.debug("Serial number: %s", self.serial_number)
            self.log.debug("Serial number list: %s", serial_number_list.value)
            if self.serial_number not in serial_number_list.value:
                raise ValueError(f"Device with serial number {self.serial_number} not found in list of serial numbers: {serial_number_list.value}")

        # Open the device
        self.lib.CC_Open(self.serial_number)
        self.lib.CC_StartPolling(self.serial_number, c_int(200))

        if self.stage_model in ['MTS25-Z8', 'MTS50-Z8', 'Z825B', 'Z806', 'Z812']:
            # Set up the device to convert real units to device units
            steps_per_rev = c_double(512)
            gear_box_ratio = c_double(67.49)
            pitch_mm = c_double(1.0)
        else:
            raise ValueError(f"Stage model {self.stage_model} not supported.")

        # Apply these values to the device
        self.lib.CC_SetMotorParamsExt(self.serial_number, steps_per_rev, gear_box_ratio, pitch_mm)

        # Read min, max, unit and model from service configuration.
        self.min_position_config = self.config['min_position']
        self.max_position_config = self.config['max_position']
        unit_config = self.config['unit']

        # Set the motor travel limits.
        min_position = c_double(self.min_position_config)
        max_position = c_double(self.max_position_config)
        self.lib.CC_SetMotorTravelLimits(self.serial_number, min_position, max_position)

        # Get the motor travel limits.
        min_position = c_double(-1)
        max_position = c_double(-1)
        self.lib.CC_GetMotorTravelLimits(self.serial_number, byref(min_position), byref(max_position))
        self.min_position_device = min_position.value
        self.max_position_device = max_position.value

        # Get the unit of the motor (mm or deg).
        self.unit_type = self.lib.CC_GetMotorTravelMode(self.serial_number)
        if self.unit_type == 1:
            self.unit = 'mm'
        elif self.unit_type == 2:
            self.unit = 'deg'

        # Compare the device parameters to the service configuration.
        if (self.min_position_device < self.min_position_config or
            self.max_position_device > self.max_position_config or
            self.unit != unit_config):
            self.log.debug("Device parameters: min=%f, max=%f, unit=%s",
                           self.min_position_device, self.max_position_device, self.unit)
            self.log.debug("Config parameters: min=%f, max=%f, unit=%s",
                           self.min_position_config, self.max_position_config, unit_config)
            self.log.debug("Device parameters don't match configuration parameters %r %r %r.",
                           self.min_position_device < self.min_position_config,
                           self.max_position_device > self.max_position_config,
                           self.unit != unit_config)
            raise ValueError("Device parameters don't match configuration parameters.")

        self.command = self.make_data_stream('command', 'float64', [1], 20)
        self.current_position = self.make_data_stream('current_position', 'float64', [1], 20)

        # Submit motor starting position to current_position data stream
        self.get_current_position()

        self.make_command('home', self.home)

        self.motor_thread = threading.Thread(target=self.monitor_motor)
        self.motor_thread.start()

    def monitor_motor(self):
        while not self.should_shut_down:
            try:
                # Get an update for the motor position.
                frame = self.command.get_next_frame(10)
                # Set the current position if a new command has arrived.
                self.set_current_position(frame.data[0])
            except RuntimeError:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def main(self):
        while not self.should_shut_down:
            self.get_current_position()
            self.sleep(self.update_interval)

    def close(self):
        self.motor_thread.join()

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
            self.log.warning('Motor not moving since commanded position is outside of configured range.')
            self.log.warning('Position limits: %f %s <= position <= %f %s.',
                             self.min_position_config, self.unit, self.max_position_config, self.unit)

        # Update the current position data stream.
        self.log.info("Setting new position: %f %s", position, self.unit)
        self.get_current_position()

    def get_current_position(self):
        current_position = self.lib.CC_GetPosition(self.serial_number)
        real_unit = c_double()
        self.lib.CC_GetRealValueFromDeviceUnit(self.serial_number, current_position, byref(real_unit), 0)
        self.current_position.submit_data(np.array([real_unit.value], dtype='float64'))

    def wait_for_completion(self):
        message_type = c_ushort()
        message_id = c_ushort()
        message_data = c_ulong()
        while message_id.value != 0 or message_type.value != 2:
            self.lib.CC_WaitForMessage(self.serial_number, byref(message_type), byref(message_id), byref(message_data))
        self.lib.CC_ClearMessageQueue(self.serial_number)
        return message_type.value, message_id.value, message_data.value

    def home(self):
        """
        Home the motor.

        This will block until the motor has finished homing.
        """
        # Home device
        self.lib.CC_ClearMessageQueue(self.serial_number)
        self.lib.CC_Home(self.serial_number)
        self.log.info("Device %s homing\r\n", self.serial_number)

        # Wait for completion
        self.log.info("Homing motor %s...", self.serial_number)
        self.wait_for_completion()
        self.log.info("Homed - motor %s", self.serial_number)

        # Update the current position data stream.
        self.get_current_position()


if __name__ == '__main__':
    service = ThorlabsCubeMotorKinesis()
    service.run()
