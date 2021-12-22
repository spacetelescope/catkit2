from catkit2.testbed.service import Service, parse_service_args
from catkit2.simulator.simulated_service import SimulatorClient

import threading
import numpy as np

class NewportPicomotorSim(Service):
    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'newport_picomotor_sim', testbed_port)

        config = self.configuration

        self.max_step = config['max_step']
        self.timeout = config['timeout']
        self.sleep_per_step = config['sleep_per_step']
        self.sleep_base = config['sleep_base']
        self.axes = config['axes']

        self.shutdown_flag = threading.Event()

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
        axis = self.axes[axis_name]

        position_before = self.get_current_position(axis_name)

        self.axis_positions[axis_name] = position

        sleep_time = self.sleep_per_step * abs(position_before - position) + self.sleep_base
        time.sleep(sleep_time)

        position_after = self.get_current_position(axis_name)

    def get_current_position(self, axis_name):
        return self.axis_positions[axis_name]

    def monitor_axis(self, axis_name):
        command_stream = self.axis_commands[axis_name]

        while not self.shutdown_flag.is_set():
            # Set the current position if a new command has arrived.
            try:
                frame = command_stream.get_next_frame(10)
            except:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            self.set_current_position(axis_name, frame.data[0])

    def open(self):
        self.shutdown_flag.clear()

        # Start the motor threads
        for axis_name in self.axes.keys():
            thread = threading.Thread(target=self.monitor_axis, args=(axis_name,))
            thread.start()

            self.axis_threads[axis_name] = thread

    def main(self):
        self.shutdown_flag.wait()

    def close(self):
        self.shut_down()

        for thread in self.axis_threads.values():
            thread.join()

    def shut_down(self):
        self.shutdown_flag.set()

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = NewportPicomotorSim(service_name, testbed_port)
    service.run()
