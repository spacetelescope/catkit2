import ctypes
import sys

TLTSP_BUFFER_SIZE = 256

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
    tsp_lib = ctypes.cdll.LoadLibrary(tsp_lib_path[0])
except Exception as error:
    tsp_lib = None
    raise ImportError("TSP01: Failed to import '{}' library @ '{}'".format(tsp_lib_name, tsp_lib_path)) from error

class ModuleTSP01(Module):
    def __init__(self):
        Module.__init__(self)

        self.shutdown_flag = False

        self.temperature_internal = self.create_data_stream('temperature_internal')
        self.humidity_internal = self.create_data_stream('humidity_internal')

        self.temperature_header_1 = self.create_data_stream('temperature_header_1')
        self.temperature_header_2 = self.create_data_stream('temperature_header_2')

    def main_thread(self):
        self.open()

        while not self.shutdown_flag:
            f = self.temperature_internal.request_new_frame()
            f.data[:] = self.get_temperature(1)
            self.temperature_internal.submit_frame(f.id)

            f = self.humidity_internal.request_new_frame()
            f.data[:] = self.get_humidity()
            self.humidity_internal.submit_frame(f.id)

            f = self.temperature_header_1.request_new_frame()
            f.data[:] = self.get_temperature(2)
            self.temperature_header_1.submit_frame(f.id)

            f = self.temperature_header_2.request_new_frame()
            f.data[:] = self.get_temperature(3)
            self.temperature_header_2.submit_frame(f.id)

            time.sleep(1)

        self.close()

    def shutdown(self):
        self.shutdown_flag = True

    def open(self):
        pass

    def find_all(self):
        device_count = ctypes.c_int(0)

        status = tsp_lib.TLTSPB_findRsrc(None, ctypes.byref(device_count))
        if status:
            raise ImportError("TSP01: Failed when trying to find connected devices - '{}'".format(self.get_error_message(status)))

        available_devices = []

        for i in range(device_count.value):
            # Create a string buffer to contain result.
            buffer = ctypes.create_string_buffer(TLTSP_BUFFER_SIZE)

            # int TLTSPB_getRsrcName(void *connection, int device_index, char *buffer)
            status = tsp_lib.TLTSPB_getRsrcName(None, i, buffer)
            if status:
                raise ImportError("TSP01: Failed when trying to find connected devices - '{}'".format(self.get_error_message(status)))

            available_devices.append(buffer.value.decode())

        return available_devices

    def get_temperature(self, channel):
        pass

    def get_humidity(self):
        pass

    def close(self):
        pass

def main():
    module = ModuleTSP01()
    module.run()

if __name__ == '__main__':
    main()
