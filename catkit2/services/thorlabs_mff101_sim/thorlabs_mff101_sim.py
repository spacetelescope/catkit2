from catkit2.testbed.service import Service

import numpy as np

class ThorlabsMFF101Sim(Service):
    def __init__(self):
        super().__init__('thorlabs_mff101_sim')

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
        self.set_position(self.out_of_beam_position)

    def set_position(self, position):
        if position == self.current_position.get()[0]:
            return

        self.current_position.submit_data(np.array([-1], dtype='int8'))

        # Send the command to the simulator. The simulator will in turn set the current position on
        # our data stream once the flip mount has been moved.
        self.testbed.simulator.move_flip_mount(flip_mount_name=self.id, new_flip_mount_position=position)

    def blink_led(self, args=None):
        self.log.info('Blinking LED.')

if __name__ == '__main__':
    service = ThorlabsMFF101Sim()
    service.run()
