from catkit2.testbed.service import Service

import time
import ftd2xx
import numpy as np
import random

class ThorlabsMFF101(Service):
    _MOVE_TO_POSITION_1 = b"\x6A\x04\x00\x01\x21\x01"
    _MOVE_TO_POSITION_2 = b"\x6A\x04\x00\x02\x21\x01"
    _BLINK_LED = b"\x23\x02\x00\x00\x21\x01"

    def __init__(self):
        super().__init__('thorlabs_mff101')

        self.serial_number = self.config['serial_number']
        self.out_of_beam_position = self.config['positions']['out_of_beam']

        self.commanded_position = self.make_data_stream('commanded_position', 'int8', [1], 20)
        self.current_position = self.make_data_stream('current_position', 'int8', [1], 20)

        self.current_position.submit_data(np.array([-1], dtype='int8'))

        self.make_command('blink_led', self.blink_led)

    def main(self):
        while not self.should_shut_down:
            try:
                frame = self.commanded_position.get_next_frame(10)
            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            position = frame.data[0]

            self.set_position(position)

    def open(self):
        num_retries = 5

        # Retry connecting to the flip mount a few times.
        while num_retries > 0:
            try:
                self.connection = ftd2xx.openEx(str(self.serial_number).encode())
            except ftd2xx.DeviceError:
                num_retries -= 1
                time.sleep(0.1 + 0.1 * random.random())

                continue
        self.connection.setDataCharacteristics(ftd2xx.defines.BITS_8,
                                               ftd2xx.defines.STOP_BITS_1,
                                               ftd2xx.defines.PARITY_NONE)
        time.sleep(.05)

        self.connection.purge()
        time.sleep(.05)

        self.connection.resetDevice()
        self.connection.setFlowControl(ftd2xx.defines.FLOW_RTS_CTS, 0, 0)
        self.connection.setRts()

        self.set_position(self.out_of_beam_position)

    def set_position(self, position):
        if position == self.current_position.get()[0]:
            return

        self.current_position.submit_data(np.array([-1], dtype='int8'))

        if position == 1:
            command = self._MOVE_TO_POSITION_1
        elif position == 2:
            command = self._MOVE_TO_POSITION_2
        else:
            # LOG error
            return

        self.connection.write(command)
        self.sleep(1)

        self.current_position.submit_data(np.array([position], dtype='int8'))

    def close(self):
        self.connection.close()
        self.connection = None

    def blink_led(self, args=None):
        self.connection.write(self._BLINK_LED)

if __name__ == '__main__':
    service = ThorlabsMFF101()
    service.run()
