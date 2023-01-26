from catkit2.testbed.service import Service

import numpy as np
import threading

class NktSuperkVariaSim(Service):
    def __init__(self):
        super().__init__('nkt_superk_varia_sim')

    def open(self):
        # Make datastreams.
        self.monitor_input = self.make_data_stream('monitor_input', [1], 'float32', 20)

        self.nd_setpoint = self.make_data_stream('nd_setpoint', [1], 'float32', 20)
        self.swp_setpoint = self.make_data_stream('swp_setpoint', [1], 'float32', 20)
        self.lwp_setpoint = self.make_data_stream('lwp_setpoint', [1], 'float32', 20)

        self.nd_filter_moving = self.make_data_stream('nd_filter_moving', [1], 'uint8', 20)
        self.swp_filter_moving = self.make_data_stream('swp_filter_moving', [1], 'uint8', 20)
        self.lwp_filter_moving = self.make_data_stream('lwp_filter_moving', [1], 'uint8', 20)

        # Set current setpoints. These will be actually set on the device
        # once the monitor threads have started.
        self.nd_setpoint.submit_data(np.array([self.config['nd_setpoint']], dtype='float32'))
        self.swp_setpoint.submit_data(np.array([self.config['swp_setpoint']], dtype='float32'))
        self.lwp_setpoint.submit_data(np.array([self.config['lwp_setpoint']], dtype='float32'))

        # Start threads.
        funcs = {
            'nd_setpoint': self.monitor(self.nd_setpoint, self.set_nd_setpoint),
            'swp_setpoint': self.monitor(self.swp_setpoint, self.set_swp_setpoint),
            'lwp_setpoint': self.monitor(self.lwp_setpoint, self.set_lwp_setpoint),
            'monitor_input': self.update_monitor_input
        }

        for key, func in funcs:
            thread = threading.Thread(target=func)
            thread.start()

            self.threads[key] = thread

    def main(self):
        # Update status.
        while not self.should_shut_down:
            self.sleep(0.5)

            self.update_status()

    def close(self):
        # Join all threads.
        for thread in self.threads:
            thread.join()

    def update_status(self):
        # Submit bogus results to their respective datastreams.
        self.nd_filter_moving.submit_data(np.array([0], dtype='uint8'))
        self.swp_filter_moving.submit_data(np.array([0], dtype='uint8'))
        self.lwp_filter_moving.submit_data(np.array([0], dtype='uint8'))

    def monitor(self, stream, setter):
        while not self.should_shut_down:
            try:
                frame = stream.get_next_frame(1)
            except Exception:
                continue

            setter(frame.data[0])

    def update_monitor_input(self):
        while not self.should_shut_down:
            self.monitor_input.submit_data(np.array([1], dtype='float32'))
            self.sleep(1)

    def set_nd_setpoint(self, nd_setpoint):
        self.simulator.move_filter(self.id + '_nd', nd_setpoint)

    def set_swp_setpoint(self, swp_setpoint):
        self.simulator.move_filter(self.id + '_swp', swp_setpoint)

    def set_lwp_setpoint(self, lwp_setpoint):
        self.simulator.move_filter(self.id + '_lwp', lwp_setpoint)

if __name__ == '__main__':
    service = NktSuperkVariaSim()
    service.run()
