'''
Thorlabs FW102C DLL simulated Service
-------------------------------------

This service is simulating the control of the Thorlabs FW102C filter wheel using the Thorlabs FW102C DLL.

'''

import time
from catkit2.testbed.service import Service


class ThorlabsFW102CDllSim(Service):
    '''
    Thorlabs FW102C DLL Service
    ---------------------------

    This class provides a simulated service to control the Thorlabs FW102C filter wheel using the Thorlabs FW102C DLL.
    It inherits from the Service class in the catkit2.testbed package.

    Attributes
    ----------
    serial : str
        The serial number of the device.

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
        super().__init__('thorlabs_fw102c_dll_sim')

        self.serial = self.config['serial']
        self.hdl = None
        self._position = 1

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
        self.log.info("Close %s successful", self._position)

    def get_position(self):
        '''
        Get the current position of the filter wheel.

        This method gets the current position of the filter wheel using the FWxCGetPosition function from the FWxC_COMMAND_LIB library.
        '''
        # self.log.info("Get Position: %d", pos[0])
        return self._position

    def set_position(self, position: int):
        '''
        Set the position of the filter wheel.

        This method sets the position of the filter wheel using the FWxCSetPosition function from the FWxC_COMMAND_LIB library.

        Parameters
        ----------
        position : int
            The position to set the filter wheel to.
        '''
        self._position = position
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
    service = ThorlabsFW102CDllSim()
    service.run()
