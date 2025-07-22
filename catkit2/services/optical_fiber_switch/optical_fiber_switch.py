from catkit2.testbed.service import Service

import serial
import threading
import numpy as np


class OpticalFiberSwitch(Service):
    COMMAND_PREFIX = b'\x01\x12\x00'  # Command prefix for setting the input channel
    COMMAND_ASK_STATUS = b'\x01\x11\x00\x00'  # Command to ask for the current status

    def __init__(self):
        super().__init__('optical_fiber_switch')
        self.port = self.config['port']
        self.baudrate = self.config['baudrate']

        self.min_channel = self.config['min_channel']
        self.max_channel = self.config['max_channel']

        self.mutex = threading.Lock()  # TODO: Use in set and get input channel methods

    def open(self):
        # Initialize the serial port connection
        self.switch = serial.Serial(
                                    port=self.port,         # Change to your port, e.g., '/dev/ttyS0' for Linux
                                    baudrate=self.baudrate,       # Adjust to your device's baud rate
                                    bytesize=serial.EIGHTBITS,
                                    parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE,
                                    timeout=1            # Timeout in seconds
                                )

        self.input_channel = self.make_data_stream('input_channel', 'int8', [1], 20)
        self.current_input = self.make_data_stream('current_input', 'int8', [1], 20)
        self.get_input_channel()

    def main(self):
        while not self.should_shut_down:
            try:
                # Get an update for the desired input.
                frame = self.input_channel.get_next_frame(10)
                # Set input channel if a new command has arrived.
                self.set_input_channel(frame.data[0])
            except RuntimeError:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

    def set_input_channel(self, channel):
        # Construct the command to set the input channel
        if channel < self.min_channel or channel > self.max_channel:
            raise ValueError(f"Channel must be between {self.min_ochannel} and {self.max_channel}.")
        command = self.COMMAND_PREFIX + bytes([channel])

        # Send the command to the switch
        try:
            self.switch.write(command)
            self.log.info(f"Switch to input channel {channel}.")
            self.sleep(0.1)
            self.get_input_channel()

        except serial.SerialException as e:
            self.log.error(f"Serial error while setting input channel: {e}")
            raise RuntimeError(f"Failed to set input channel: {e}")

    def get_input_channel(self):
        # Ask for the status after setting the channel
        self.switch.write(self.COMMAND_ASK_STATUS)
        self.sleep(0.1)

        # Read the response
        response = self.switch.read(4)
        if len(response) == 4:
            self.log.info(f"Received response: {response}")
            current_channel = str(response)[-2]  # Get the channel number which is before the closing quote
            self.current_input.submit_data(np.array([current_channel], dtype='int8'))
        else:
            self.log.warning(f"Incomplete response: {response}")

    def close(self):
        self.switch.close()


if __name__ == '__main__':
    optical_switch = OpticalFiberSwitch()
    optical_switch.run()
