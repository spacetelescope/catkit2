from catkit2.protocol.service import Service, parse_service_args
from catkit2.simulator.simulated_service import SimulatorClient

import threading
import numpy as np

class NewportXpsQ8Sim(Service):
    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'newport_xps_q8_sim', testbed_port)

        config = self.configuration

        self.motor_positions = config['motors']
        self.update_interval = config['update_interval']
        self.motor_ids = list(config['motors'].keys())

        self.shutdown_flag = threading.Event()

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

        while not self.shutdown_flag.is_set():
            # Set the current position if a new command has arrived.
            try:
                frame = command_stream.get_next_frame(10)
            except:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            self.set_current_position(motor_id, frame.data[0])

    def open(self):
        self.shutdown_flag.clear()

        # Start the motor threads
        for motor_id in self.motor_ids:
            thread = threading.Thread(target=self.monitor_motor, args=(motor_id,))
            thread.start()

            self.motor_threads[motor_id] = thread

    def main(self):
        while not self.shutdown_flag.is_set():
            for motor_id in self.motor_ids:
                self.get_current_position(motor_id)

            self.shutdown_flag.wait(self.update_interval)

    def close(self):
        # Stop the motor threads
        self.shut_down()

        for thread in self.motor_threads.values():
            thread.join()

        self.motor_threads = {}

    def shut_down(self):
        self.shutdown_flag.set()

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = NewportXpsQ8Sim(service_name, testbed_port)
    service.run()
