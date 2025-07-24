from catkit2.testbed.service import Service
import numpy as np


class OpticalFiberSwitchSim(Service):
    COMMAND_PREFIX = b'\x01\x12\x00'  # Command prefix for setting the input channel
    COMMAND_ASK_STATUS = b'\x01\x11\x00\x00'  # Command to ask for the current status

    def __init__(self):
        super().__init__('optical_fiber_switch_sim')
        self.port = self.config['port']
        self.baudrate = self.config['baudrate']

        self.min_channel = self.config['min_channel']
        self.max_channel = self.config['max_channel']

    def open(self):
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
            raise ValueError(f"Channel must be between {self.min_channel} and {self.max_channel}.")

        self.testbed.simulator.set_source_power(source_name=self.id, power=channel)
        self.log.info(f"Switch to input channel {channel}.")
        self.sleep(0.1)
        self.get_input_channel()

    def get_input_channel(self):
        current_channel = self.input_channel.get()[0]  # Yes, total hack
        self.current_input.submit_data(np.array([current_channel], dtype='int8'))

    def close(self):
        pass


if __name__ == '__main__':
    optical_switch = OpticalFiberSwitchSim()
    optical_switch.run()
