from catkit2.catkit_bindings import Module, DataStream, Command, Property
from catkit2.testbed import parse_module_args

import time
import pyvisa

class ThorlabsFW102CModule(Module):
    _GET_POSITION = "pos?"
    _SET_POSITION = "pos="
    _MAX_NUM_RETRIES = 3

    def __init__(self):
        args = parse_module_args()
        Module.__init__(self, args.module_name, args.module_port)

        testbed = Testbed(args.testbed_server_port)
        config = testbed.config['modules'][args.module_name]

        self.visa_id = config['visa_id']
        self.current_position = None

        self.shutdown_flag = False

        self.position = DataStream.create('position', self.name, 'int8', [1], 20)
        self.register_data_stream(self.position)

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
                except:
                    if num_retries == 0:
                        raise

                    num_retries -= 1

                    self.close()
                    self.open()

    def shut_down(self):
        self.shutdown_flag = True

    def open(self):
        manager = pyvisa.ResourceManager('@py')

        self.connection = manager.open_resource(self.visa_id,
                                                baud_rate=115200,
                                                data_bits=8,
                                                write_termination='\r',
                                                read_termination='\r')

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
        if position == self.current_position:
            return

        self.send_command(f'{self._SET_POSITION}{position}')
        self.current_position = position

    def close(self):
        self.connection.close()
        self.connection = None

def main():
    module = ThorlabsMFF101Module()
    module.run()

if __name__ == '__main__':
    main()
