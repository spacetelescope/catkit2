from catkit2.testbed.service import Service
from catkit2.simulator.simulated_service import SimulatorClient

import threading
import numpy as np

class NewportXpsQ8Sim(Service):
    def __init__(self):
        super().__init__('newport_xps_q8_sim')

        self.motor_positions = self.config['motors']
        self.update_interval = self.config['update_interval']
        self.motor_ids = list(self.config['motors'].keys())

        self.motor_commands = {}
        self.motor_current_positions = {}
        self.motor_threads = {}

        self.motor_sim_positions = {}

        for motor_id in self.motor_ids:
            self.add_motor(motor_id)

    def add_motor(self, motor_id):
        self.motor_commands[motor_id] = self.make_data_stream(motor_id.lower() + '_command', 'float64', [1], 20)
        self.motor_current_positions[motor_id] = self.make_data_stream(motor_id.lower() + '_current_position', 'float64', [1], 20)
        self.motor_sim_positions[motor_id] = 0.0

    def set_current_position(self, motor_id, position):
        self.motor_sim_positions[motor_id] = position

    def get_current_position(self, motor_id):
        current_position = self.motor_sim_positions[motor_id]

        # Update current position data stream.
        stream = self.motor_current_positions[motor_id]
        stream.submit_data(np.array([current_position]))

        return current_position

    def monitor_motor(self, motor_id):
        command_stream = self.motor_commands[motor_id]

        while not self.should_shut_down:
            # Set the current position if a new command has arrived.
            try:
                frame = command_stream.get_next_frame(10)
            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            self.set_current_position(motor_id, frame.data[0])

    def open(self):
        # Start the motor threads
        for motor_id in self.motor_ids:
            thread = threading.Thread(target=self.monitor_motor, args=(motor_id,))
            thread.start()

            self.motor_threads[motor_id] = thread

    def main(self):
        while not self.should_shut_down:
            for motor_id in self.motor_ids:
                self.get_current_position(motor_id)

            self.sleep(self.update_interval)

    def close(self):
        # Stop the motor threads
        self.shut_down()

        for thread in self.motor_threads.values():
            thread.join()

        self.motor_threads = {}

if __name__ == '__main__':
    service = NewportXpsQ8Sim()
    service.run()
