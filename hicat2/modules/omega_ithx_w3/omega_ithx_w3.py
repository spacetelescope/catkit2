from hicat2.bindings import Module, DataStream, Command, Property
from hicat2.testbed import parse_module_args

import time
import socket

class OmegaIthxW3Module(Module):
    _ADDRESS_FAMILY = socket.AF_INET
    _SOCKET_KIND = socket.SOCK_STREAM
    _BLOCKING = True
    _TIMEOUT = 60
    _BUFFER_SIZE = 1024

    _GET_TEMPERATURE_C = b"*SRTC\r"
    _GET_HUMIDITY = b"*SRH\r"
    _GET_TEMPERATURE_AND_HUMIDITY = b"*SRB\r"

    def __init__(self):
        args = parse_module_args()
        Module.__init__(self, args.module_name, args.module_port)

        testbed = Testbed(args.testbed_server_port)
        config = testbed.config['modules'][args.module_name]

        self.ip_address = config['ip_address']
        self.port = 2000
        self.time_interval = config['time_interval']

        self.shutdown_flag = False

        self.temperature = DataStream.create('temperature', self.name, 'float64', [1], 20)
        self.register_data_stream(self.temperature)

        self.humidity = DataStream.create('humidity', self.name, 'float64', [1], 20)
        self.register_data_stream(self.humidity)

    def main(self):
        while not self.shutdown_flag:
            start = time.time()

            temp, hum = self.get_temperature_and_humidity()

            f = self.temperature.request_new_frame()
            f.data[:] = temp
            self.temperature.submit_frame(f.id)

            f = self.humidity.request_new_frame()
            f.data[:] = hum
            self.humidity.submit_frame(f.id)

            while (time.time() < (start + self.time_interval)) and not self.shutdown_flag:
                time.sleep(0.01)

    def shut_down(self):
        self.shutdown_flag = True

    def open(self):
        self.connection = socket.socket(self._ADDRESS_FAMILY, self._SOCKET_KIND)
        self.connection.setblocking(self._BLOCKING)
        self.connection.settimeout(self._TIMEOUT)

        self.connection.connect((self.host, self.port))

    def get_response(self):
        data = self.connection.recv(self.BUFFER_SIZE)

        if data is None or not len(data):
            raise OSError(f"{self.config_id}: Unexpected error - no data received.")

        # Parse response. Example b"03.36\r" or b"03.36\r,45.2\r".
        data = re.findall("[\+\-0-9.]+", data.decode())

        # Convert to float.
        data = [float(item) for item in data]

        if len(data) == 1:
            return data[0]
        else:
            return tuple(data)

    def get_temperature(self):
        self.connection.sendall(self._GET_TEMPERATURE_C)
        return self.get_response()

    def get_humidity(self):
        self.connection.sendall(self._GET_HUMIDITY)
        return self.get_response()

    def get_temperature_and_humidity(self):
        self.connection.sendall(self._GET_TEMPERATURE_AND_HUMIDITY)
        return self.get_response()

    def close(self):
        self.connection.close()
        self.connection = None

def main():
    module = OmegaIthxW3Module()
    module.run()

if __name__ == '__main__':
    main()
