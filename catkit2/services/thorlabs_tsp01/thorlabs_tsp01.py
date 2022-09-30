import ctypes
import sys
import glob
import os
import numpy as np

from catkit2.testbed.service import Service

class ThorlabsTSP01(Service):
    _BUFFER_SIZE = 256

    def __init__(self):
        super().__init__('thorlabs_tsp01')

        self.serial_number = self.config['serial_number']
        self.num_averaging = self.config.get('averaging', 1)
        self.interval = self.config.get('interval', 10)

        self.temperature_internal = self.make_data_stream('temperature_internal', 'float64', [1], 20)
        self.temperature_header_1 = self.make_data_stream('temperature_header_1', 'float64', [1], 20)
        self.temperature_header_2 = self.make_data_stream('temperature_header_2', 'float64', [1], 20)
        self.humidity_internal = self.make_data_stream('humidity_internal', 'float64', [1], 20)

    def main(self):
        while not self.should_shut_down:
            temperature = self.get_temperature(1)
            self.temperature_internal.submit_data(np.array([temperature]))

            temperature = self.get_temperature(2)
            self.temperature_header_1.submit_data(np.array([temperature]))

            temperature = self.get_temperature(3)
            self.temperature_header_2.submit_data(np.array([temperature]))

            humidity = self.get_humidity()
            self.humidity_internal.submit_data(np.array([humidity]))

            self.sleep(self.interval)

    def load_library(self):
        tsp_lib_name = "TLTSPB_64.dll"  # Yep, this is Windows specific.
        tsp_lib_path = None

        for path in sys.path:
            tsp_lib_path = glob.glob(os.path.join(path, tsp_lib_name))

            if tsp_lib_path:
                break

        if not tsp_lib_path:
            raise ImportError("TSP01: Failed to locate '{}' - add path to PYTHONPATH".format(tsp_lib_name))

        # Now load the found library.
        try:
            self.lib = ctypes.cdll.LoadLibrary(tsp_lib_path[0])
        except Exception as error:
            self.lib = None
            raise ImportError("TSP01: Failed to import '{}' library @ '{}'".format(tsp_lib_name, tsp_lib_path)) from error

    def get_error_message(self, status_code):
        """Convert error status to error message."""
        error_message = ctypes.create_string_buffer(self._BUFFER_SIZE)

        # int TLTSPB_errorMessage(void * connection, int status_code, char * error_message)
        status = self.lib.TLTSPB_errorMessage(None, status_code, error_message)
        if status:
            raise OSError("TSP01: Ironically failed to get error message - '{}'".format(self.get_error_message(status)))
        return error_message.value.decode()

    def open(self):
        self.load_library()

        self.instrument = ctypes.c_void_p(None)

        # Find the desired device resource name. This is not just the SN#.
        # NOTE: The revB call only finds revB devices.
        available_devices = self.find_all()
        self.device_name = [device for device in available_devices if self.serial_number in device]

        if not self.device_name:
            raise OSError("TSP01: device not found - SN# '{}'".format(self.serial_number))

        if len(self.device_name) > 1:
            raise OSError("TSP01: found multiple devices with the same SN# '{}'".format(self.serial_number))

        self.device_name = self.device_name[0]

        # int TLTSPB_init(char * device_name, bool id_query, bool reset_device, void ** connection)
        status = self.lib.TLTSPB_init(self.device_name.encode(), True, True, ctypes.byref(self.instrument))

        if status or self.instrument.value is None:
            raise OSError("TSP01: Failed to connect - '{}'".format(self.get_error_message(status)))

    def find_all(self):
        device_count = ctypes.c_int(0)
        status = self.lib.TLTSPB_findRsrc(None, ctypes.byref(device_count))

        if status:
            raise ImportError("TSP01: Failed when trying to find connected devices - '{}'".format(self.get_error_message(status)))

        available_devices = []

        for i in range(device_count.value):
            # Create a string buffer to contain result.
            buffer = ctypes.create_string_buffer(self._BUFFER_SIZE)

            # int TLTSPB_getRsrcName(void *connection, int device_index, char *buffer)
            status = self.lib.TLTSPB_getRsrcName(None, i, buffer)

            if status:
                raise ImportError("TSP01: Failed when trying to find connected devices - '{}'".format(self.get_error_message(status)))

            available_devices.append(buffer.value.decode())

        return available_devices

    def get_temperature(self, channel):
        average_temperature = 0

        for _ in range(self.num_averaging):
            temp = ctypes.c_double(0)

            # int TLTSPB_getTemperatureData(void * connection, int channel, double * temp)
            status = self.lib.TLTSPB_measTemperature(self.instrument, int(channel) + 10, ctypes.byref(temp))

            if status:
                raise RuntimeError("TSP01: Failed to get temperature - '{}'".format(self.get_error_message(status)))

            average_temperature += temp.value

        return average_temperature / self.num_averaging

    def get_humidity(self):
        average_humidity = 0

        for _ in range(self.num_averaging):
            hum = ctypes.c_double(0)

            # int TLTSPB_getHumidityData(void * connection, ?, double * humidity)
            status = self.lib.TLTSPB_measHumidity(self.instrument, ctypes.byref(hum))

            if status:
                raise RuntimeError("TSP01: Failed to get humidity - '{}'".format(self.get_error_message(status)))

            average_humidity += hum.value

        return average_humidity / self.num_averaging

    def close(self):
        if self.instrument.value:
            # int TLTSPB_close(void * connection)
            status = self.lib.TLTSPB_close(self.instrument)

            if status:
                pass  # Don't do anything with this.

            self.instrument = ctypes.c_void_p(None)

if __name__ == '__main__':
    service = ThorlabsTSP01()
    service.run()
