import ctypes
import sys
import glob
import os
import time
import numpy as np

from catkit2.testbed.service import Service

class ThorlabsPM(Service):
    _BUFFER_SIZE = 256

    def __init__(self):
        super().__init__('thorlabs_pm')

        self.serial_number = str(self.config['serial_number'])
        self.interval = self.config.get('interval', 10)

        self.power = self.make_data_stream('power', 'float64', [1], 20)

    def main(self):
        while not self.should_shut_down:
            power = self.get_power()
            self.power.submit_data(np.array([power]))

            self.sleep(self.interval)

    def load_library(self):
        library_name = "TLPM_64.dll"  # Yep, this is Windows specific.
        library_path = None

        for path in sys.path:
            library_path = glob.glob(os.path.join(path, library_name))

            if library_path:
                break

        if not library_path:
            raise ImportError("TLPM: Failed to locate '{}' - add path to PYTHONPATH".format(library_name))

        # Now load the found library.
        try:
            self.lib = ctypes.cdll.LoadLibrary(library_path[0])
        except Exception as error:
            self.lib = None
            raise ImportError("TLPM: Failed to import '{}' library @ '{}'".format(library_name, library_path)) from error

    def get_error_message(self, status_code):
        """Convert error status to error message."""
        error_message = ctypes.create_string_buffer(self._BUFFER_SIZE)

        # int TLPM_errorMessage(void *vi, int statusCode, char description[])
        status = self.lib.TLPM_errorMessage(None, status_code, error_message)
        if status:
            raise OSError("TLPM: Ironically failed to get error message - '{}'".format(self.get_error_message(status)))
        return error_message.value.decode()

    def open(self):
        self.load_library()

        self.instrument = ctypes.c_void_p(None)

        # Find the desired device resource name. This is not just the SN#.
        # NOTE: The revB call only finds revB devices.
        available_devices = self.find_all()
        device_names = [device for device in available_devices if self.serial_number in device]

        if not device_names:
            raise OSError("TLPM: device not found - SN# '{}'".format(self.serial_number))

        if len(device_names) > 1:
            raise OSError("TLPM: found multiple devices with the same SN# '{}'".format(self.serial_number))

        self.device_name = device_names[0]

        # int TLPM_init(char *resourceName, bool IDQuery, bool resetDevice, void **vi)
        status = self.lib.TLPM_init(self.device_name.encode(), True, True, ctypes.byref(self.instrument))

        if status or self.instrument.value is None:
            raise OSError("TLPM: Failed to connect - '{}'".format(self.get_error_message(status)))

    def find_all(self):
        device_count = ctypes.c_int(0)

        # int TLPM_findRsrc(void *vi, int *resourceCount)
        status = self.lib.TLPM_findRsrc(None, ctypes.byref(device_count))

        if status:
            raise ImportError("TLPM: Failed when trying to find connected devices - '{}'".format(self.get_error_message(status)))

        available_devices = []

        for i in range(device_count.value):
            # Create a string buffer to contain result.
            buffer = ctypes.create_string_buffer(self._BUFFER_SIZE)

            # int TLPM_getRsrcName(void *vi, int device_index, char resourceName[])
            status = self.lib.TLPM_getRsrcName(None, i, buffer)

            if status:
                raise ImportError("TLPM: Failed when trying to find connected devices - '{}'".format(self.get_error_message(status)))

            available_devices.append(buffer.value.decode())

        return available_devices

    def get_power(self):
        power = ctypes.c_double(0)

        # int TLPM_measPower(void *vi, double *power);
        status = self.lib.TLPM_measPower(self.instrument, ctypes.byref(power))

        if status:
            raise RuntimeError("TLPM: Failed to get power - '{}'".format(self.get_error_message(status)))

        return power.value

    def close(self):
        if self.instrument.value:
            # int TLPM_close(void *vi)
            status = self.lib.TLPM_close(self.instrument)

            if status:
                pass  # Don't do anything with this.

            self.instrument = ctypes.c_void_p(None)

if __name__ == '__main__':
    service = ThorlabsPM()
    service.run()
