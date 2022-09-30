from catkit2.testbed.service import Service

import time
import socket
import re
import numpy as np

class OmegaIthxW3(Service):
    _ADDRESS_FAMILY = socket.AF_INET
    _SOCKET_KIND = socket.SOCK_STREAM
    _BLOCKING = True
    _TIMEOUT = 60
    _BUFFER_SIZE = 1024

    _GET_TEMPERATURE_C = b"*SRTC\r"
    _GET_HUMIDITY = b"*SRH\r"
    _GET_TEMPERATURE_AND_HUMIDITY = b"*SRB\r"

    def __init__(self):
        super().__init__('omega_ithx_w3')

        self.ip_address = self.config['ip_address']
        self.port = 2000
        self.time_interval = self.config['time_interval']

        self.temperature = self.make_data_stream('temperature', 'float64', [1], 20)
        self.humidity = self.make_data_stream('humidity', 'float64', [1], 20)

    def main(self):
        while not self.should_shut_down:
            start = time.time()

            temp, hum = self.get_temperature_and_humidity()

            self.temperature.submit_data(np.array([temp]))
            self.humidity.submit_data(np.array([hum]))

            time_remaining = self.time_interval - (time.time() - start)
            self.sleep(time_remaining)

    def open(self):
        self.connection = socket.socket(self._ADDRESS_FAMILY, self._SOCKET_KIND)
        self.connection.setblocking(self._BLOCKING)
        self.connection.settimeout(self._TIMEOUT)

        self.connection.connect((self.ip_address, self.port))

    def get_response(self):
        data = self.connection.recv(self._BUFFER_SIZE)

        if data is None or not len(data):
            raise OSError(f"{self.config_id}: Unexpected error - no data received.")

        # Parse response. Example b"03.36\r" or b"03.36\r,45.2\r".
        data = re.findall(r"[\+\-0-9.]+", data.decode())

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

if __name__ == '__main__':
    service = OmegaIthxW3()
    service.run()
