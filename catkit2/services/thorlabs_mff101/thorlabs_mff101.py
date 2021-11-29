from catkit2.bindings import Module, DataStream, Command, Property
from catkit2.testbed import parse_module_args

import time
import ftd2xx

class ThorlabsMFF101Module(Module):
    _MOVE_TO_POSITION_1 = b"\x6A\x04\x00\x01\x21\x01"
    _MOVE_TO_POSITION_2 = b"\x6A\x04\x00\x02\x21\x01"
    _BLINK_LED = b"\x23\x02\x00\x00\x21\x01"

    def __init__(self):
        args = parse_module_args()
        Module.__init__(self, args.module_name, args.module_port)

        testbed = Testbed(args.testbed_server_port)
        config = testbed.config['modules'][args.module_name]

        self.serial_number = config['serial_number']
        self.current_position = None

        self.shutdown_flag = False

        self.position = DataStream.create('position', self.name, 'int8', [1], 20)
        self.register_data_stream(self.position)

        self.register_command(Command('blink_led', self.blink_led))

    def main(self):
        while not self.shutdown_flag:
            try:
                frame = self.position.get_next_frame(10)
            except:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            position = frame.data[0]

            self.set_position(position)

    def shut_down(self):
        self.shutdown_flag = True

    def open(self):
        self.connection = ftd2xx.openEx(self.serial_number.encode())
        self.connection.setDataCharacteristics(ftd2xx.defines.BITS_8,
                                               ftd2xx.defines.STOP_BITS_1,
                                               ftd2xx.defines.PARITY_NONE)
        time.sleep(.05)

        self.connection.purge()
        time.sleep(.05)

        self.connection.resetDevice()
        self.connection.setFlowControl(ftd2xx.defines.FLOW_RTS_CTS, 0, 0)
        self.connection.setRts()

    def set_position(self, position):
        if position == self.current_position:
            return

        if position == 1:
            command = self._MOVE_TO_POSITION_1
        elif position == 2:
            command = self._MOVE_TO_POSITION_2
        else:
            # LOG error
            continue

        self.connection.write(command)
        self.current_position = position

    def close(self):
        self.connection.close()
        self.connection = None

    def blink_led(self, args=None):
        self.connection.write(self._BLINK_LED)

def main():
    module = ThorlabsMFF101Module()
    module.run()

if __name__ == '__main__':
    main()
