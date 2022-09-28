from catkit2.testbed.service import Service

import threading
import time

class NewportPicomotorSim(Service):
    def __init__(self):
        super().__init__('newport_picomotor_sim')

        self.max_step = self.config['max_step']
        self.timeout = self.config['timeout']
        self.sleep_per_step = self.config['sleep_per_step']
        self.sleep_base = self.config['sleep_base']
        self.axes = self.config['axes']

        self.axis_commands = {}
        self.axis_current_positions = {}
        self.axis_threads = {}
        self.axis_positions = {}

        for axis_name in self.axes.keys():
            self.add_axis(axis_name)

    def add_axis(self, axis_name):
        self.axis_commands[axis_name] = self.make_data_stream(axis_name.lower() + '_command', 'int64', [1], 20)
        self.axis_current_positions[axis_name] = self.make_data_stream(axis_name.lower() + '_current_position', 'int64', [1], 20)
        self.axis_positions[axis_name] = 0

    def set_current_position(self, axis_name, position):
        position_before = self.get_current_position(axis_name)

        self.axis_positions[axis_name] = position

        sleep_time = self.sleep_per_step * abs(position_before - position) + self.sleep_base
        time.sleep(sleep_time)

    def get_current_position(self, axis_name):
        return self.axis_positions[axis_name]

    def monitor_axis(self, axis_name):
        command_stream = self.axis_commands[axis_name]

        while not self.should_shut_down:
            # Set the current position if a new command has arrived.
            try:
                frame = command_stream.get_next_frame(10)
            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            self.set_current_position(axis_name, frame.data[0])

    def open(self):
        # Start the motor threads
        for axis_name in self.axes.keys():
            thread = threading.Thread(target=self.monitor_axis, args=(axis_name,))
            thread.start()

            self.axis_threads[axis_name] = thread

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        self.shut_down()

        for thread in self.axis_threads.values():
            thread.join()

if __name__ == '__main__':
    service = NewportPicomotorSim()
    service.run()
