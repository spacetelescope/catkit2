from catkit2.protocol.service import Service, parse_service_args

import time
import pyvisa
import numpy as np

class ThorlabsFW102C(Service):
    _GET_POSITION = "pos?"
    _SET_POSITION = "pos="
    _MAX_NUM_RETRIES = 3

    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'thorlabs_fw102c', testbed_port)

        config = self.configuration

        self.visa_id = config['visa_id']

        self.shutdown_flag = False

        self.position = self.make_data_stream('position', 'int8', [1], 20)
        self.current_position = self.make_data_stream('current_position', 'int8', [1], 20)

    def open(self):
        manager = pyvisa.ResourceManager('@py')

        self.connection = manager.open_resource(self.visa_id,
                                                baud_rate=115200,
                                                data_bits=8,
                                                write_termination='\r',
                                                read_termination='\r')

    def main(self):
        while not self.shutdown_flag:
            num_retries = self._MAX_NUM_RETRIES

            try:
                frame = self.position.get_next_frame(10)
            except:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            position = frame.data[0]

            # Try setting the position a few times before giving up.
            while True:
                try:
                    self.set_position(position)
                    break
                except Exception:
                    if num_retries == 0:
                        raise

                    num_retries -= 1

                    self.close()
                    self.open()

    def close(self):
        self.connection.close()
        self.connection = None

    def shut_down(self):
        self.shutdown_flag = True

    def send_command(self, command):
        try:
            bytes_written = self.connection.write(command)

            if self.connection.last_status is visapy.constants.StatusCode.success:
                # Read the echo.
                self.connection.read()
            else:
                raise RuntimeError(f'Filter wheel returned an unexpected response: {self.instrument.last_status}.')
        except:
            self.current_position = None
            raise

    def set_position(self, position):
        try:
            if position == self.current_position.get():
                return
        except Exception:
            # No previous position known.
            pass

        self.send_command(f'{self._SET_POSITION}{position}')

        self.current_position.submit_data(np.array([current_position]))

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = ThorlabsFW102C(service_name, testbed_port)
    service.run()
