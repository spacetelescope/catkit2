'''
Thorlabs FW102C DLL Service
---------------------------

This service is used to control the Thorlabs FW102C filter wheel using the Thorlabs FW102C DLL.

The Thorlabs FW102C filter wheel SDK is available at https://www.thorlabs.com/software_pages/ViewSoftwarePage.cfm?Code=FW102C

The original FWxC_COMMAND_LIB.py file is located at c://Program Files (x86)//Thorlabs//FWxC//Sample//Thorlabs_FWxC_PythonSDK
The original FWxC_COMMAND_LIB.py file loads the FilterWheel102_win32.dll file instead of the FilterWheel102_win64.dll file
'''

import time
from catkit2.testbed.service import Service

try:
    from FWxC_COMMAND_LIB import (
        FWxCOpen,
        FWxCClose,
        FWxCGetPosition,
        FWxCSetPosition,
        FWxCListDevices,
        FWxCSetTriggerMode,
        FWxCSetSpeedMode,
        FWxCSetSensorMode
    )
except OSError as ex:
    print("Warning:", ex)


class ThorlabsFW102CDll(Service):
    '''
    Thorlabs FW102C DLL Service
    ---------------------------

    This class provides a service to control the Thorlabs FW102C filter wheel using the Thorlabs FW102C DLL.
    It inherits from the Service class in the catkit2.testbed package.

    Attributes
    ----------
    serial : str
        The serial number of the device.
    hdl : int
        The handle of the device.

    Methods
    -------
    __init__():
        Initializes the ThorlabsFW102CDll service.
    open():
        Opens a connection to the device.
    main():
        Main loop that keeps the service running.
    close():
        Closes the connection to the device.
    get_position():
        Gets the current position of the filter wheel.
    set_position(position: int):
        Sets the position of the filter wheel.
    position:
        Property that gets or sets the position of the filter wheel.
    '''
    def __init__(self):
        '''
        Initialize the ThorlabsFW102CDll service.

        This method initializes the ThorlabsFW102CDll service by calling the __init__ method of the superclass with 'thorlabs_fw102c_dll' as the argument.
        It also initializes the serial number of the device and the handle of the device.
        '''
        super().__init__('thorlabs_fw102c_dll')

        self.serial = self.config['serial']
        devs = FWxCListDevices()
        if len(devs) <= 0:
            raise RuntimeError("There is no devices connected")
        if self.serial not in [dev[0] for dev in devs]:
            raise RuntimeError("Device %s not found", self.serial)
        self.hdl = None

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

        make_property_helper('position', dtype='int64')

        # self.make_command('get_position', self.get_position)
        # self.make_command('set_position', self.set_position)

    def open(self):
        '''
        Open a connection to the device.

        This method opens a connection to the device using the FWxCOpen function from the FWxC_COMMAND_LIB library.
        It also sets the input trigger mode, high speed mode, and turn off the sensor of the device.
        '''
        self.hdl = FWxCOpen(self.serial, 115200, 3)
        if self.hdl < 0:
            raise RuntimeError(f"Connect {self.serial} fail")

        # 0: input mode, 1: output mode
        result = FWxCSetTriggerMode(self.hdl, 0)
        if result < 0:
            self.log.warning("Set Trigger Mode fail")

        # 0: slow speed, 1: high speed
        result = FWxCSetSpeedMode(self.hdl, 1)
        if result < 0:
            self.log.warning("Set Speed Mode fail")

        # 0: Sensors turn off, 1: Sensors remain active
        result = FWxCSetSensorMode(self.hdl, 0)
        if result < 0:
            self.log.warning("Set Sensor Mode fail")

        self.log.info("Connect %s successful", self.serial)

    def main(self):
        '''
        Main loop that keeps the service running.

        This method keeps the service running until it should shut down.
        '''
        while not self.should_shut_down:
            time.sleep(0.1)

    def close(self):
        '''
        Close the connection to the device.

        This method closes the connection to the device using the FWxCClose function from the FWxC_COMMAND_LIB library.
        '''
        if self.hdl is None:
            raise RuntimeError("Device not connected")
        FWxCClose(self.hdl)
        self.log.info("Close %s successful", self.serial)

    def get_position(self):
        '''
        Get the current position of the filter wheel.

        This method gets the current position of the filter wheel using the FWxCGetPosition function from the FWxC_COMMAND_LIB library.
        '''
        if self.hdl is None:
            return -1
        pos = [-1]

        result = FWxCGetPosition(self.hdl, pos)
        if result < 0 and pos[0] < 0:
            self.log.error("Get Position fail")
            return -1

        # self.log.info("Get Position: %d", pos[0])
        return pos[0]

    def set_position(self, position: int):
        '''
        Set the position of the filter wheel.

        This method sets the position of the filter wheel using the FWxCSetPosition function from the FWxC_COMMAND_LIB library.

        Parameters
        ----------
        position : int
            The position to set the filter wheel to.
        '''
        if self.hdl is None:
            raise RuntimeError("Device not connected")
        result = FWxCSetPosition(self.hdl, position)
        if result < 0:
            self.log.error("Set Position fail")
            return -1

        self.log.info("Position is %d", position)

    @property
    def position(self):
        '''
        Get or set the position of the filter wheel.

        This property gets or sets the position of the filter wheel using the get_position and set_position methods.
        '''
        return self.get_position()

    @position.setter
    def position(self, position: int):
        return self.set_position(position)


if __name__ == '__main__':
    service = ThorlabsFW102CDll()
    service.run()
