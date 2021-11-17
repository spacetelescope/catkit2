import ctypes
import sys
import glob
import os

# Disable the Fortran Ctrl-C handler as it interferes with safe closing of
# the service.
os.environ['FOR_DISABLE_CONSOLE_CTRL_HANDLER'] = '1'

from hicat2.protocol.service import Service, parse_service_args

class ThorlabsTSP01(Serivce):
    _BUFFER_SIZE = 256

    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'thorlabs_tsp01', testbed_port)

        config = self.configuration
        self.serial_number = config['serial_number']

        self.shutdown_flag = False

        self.temperature_internal = self.make_data_stream('temperature_internal', 'float64', [1], 20)
        self.temperature_header_1 = self.make_data_stream('temperature_header_1', 'float64', [1], 20)
        self.temperature_header_2 = self.make_data_stream('temperature_header_2', 'float64', [1], 20)
        self.humidity_internal = self.make_data_stream('humidity_internal', 'float64', [1], 20)

    def main(self):
        while not self.shutdown_flag:
            t1 = self.get_temperature(1)
            t2 = self.get_temperature(2)
            t3 = self.get_temperature(3)
            h = self.get_humidity()

            self.temperature_internal.submit_data(np.array([t1]))
            self.temperature_header_1.submit_data(np.array([t2]))
            self.temperature_header_2.submit_data(np.array([t3]))
            self.humidity_internal.submit_data(np.array([h]))

            time.sleep(1)

    def shutdown(self):
        self.shutdown_flag = True

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

    def get_error_message(cls, status_code):
        """Convert error status to error message."""
        error_message = ctypes.create_string_buffer(self._BUFFER_SIZE)

        # int TLTSPB_errorMessage(void * connection, int status_code, char * error_message)
        status = self.lib.TLTSPB_errorMessage(None, status_code, error_message)
        if status:
            raise OSError("TSP01: Ironically failed to get error message - '{}'".format(self.get_error_message(status)))
        return error_message.value.decode()

    def open(self):
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
        temp = ctypes.c_double(0)

        # int TLTSPB_getTemperatureData(void * connection, int channel, double * temp)
        status = self.lib.TLTSPB_measTemperature(self.instrument, int(channel), ctypes.byref(temp))

        if status:
            raise RuntimeError("TSP01: Failed to get temperature - '{}'".format(self.get_error_message(status)))

        return temp.value

    def get_humidity(self):
        humidity = ctypes.c_double(0)

        # int TLTSPB_getHumidityData(void * connection, ?, double * humidity)
        status = self.lib.TLTSPB_measHumidity(self.instrument, ctypes.byref(humidity))

        if status:
            raise RuntimeError("TSP01: Failed to get humidity - '{}'".format(self.get_error_message(status)))

        return humidity.value

    def close(self):
        if self.instrument.value:
            # int TLTSPB_close(void * connection)
            status = self.lib.TLTSPB_close(self.instrument)

            if status:
                pass  # Don't do anything with this.

            self.instrument = ctypes.c_void_p(None)

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = ThorlabsTSP01(service_name, testbed_port)
    service.run()
