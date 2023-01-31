from catkit2.testbed.service import Service

import numpy as np
import threading


class NktSuperkSim(Service):
    def __init__(self):
        super().__init__('nkt_superk_sim')

        self.threads = {}
        self.port = self.config['port']

    def open(self):
        # Make datastreams.
        self.base_temperature = self.make_data_stream('base_temperature', 'float32', [1], 20)
        self.supply_voltage = self.make_data_stream('supply_voltage', 'float32', [1], 20)
        self.external_control_input = self.make_data_stream('external_control_input', 'float32', [1], 20)

        self.emission = self.make_data_stream('emission', 'uint8', [1], 20)
        self.power_setpoint = self.make_data_stream('power_setpoint', 'float32', [1], 20)
        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)

        self.monitor_input = self.make_data_stream('monitor_input', 'float32', [1], 20)

        self.nd_setpoint = self.make_data_stream('nd_setpoint', 'float32', [1], 20)
        self.swp_setpoint = self.make_data_stream('swp_setpoint', 'float32', [1], 20)
        self.lwp_setpoint = self.make_data_stream('lwp_setpoint', 'float32', [1], 20)

        self.nd_filter_moving = self.make_data_stream('nd_filter_moving', 'uint8', [1], 20)
        self.swp_filter_moving = self.make_data_stream('swp_filter_moving', 'uint8', [1], 20)
        self.lwp_filter_moving = self.make_data_stream('lwp_filter_moving', 'uint8', [1], 20)

        # Set current setpoints. These will be actually set on the device
        # once the monitor threads have started.
        self.emission.submit_data(np.array([self.config['emission']], dtype='uint8'))
        self.power_setpoint.submit_data(np.array([self.config['power_setpoint']], dtype='float32'))
        self.current_setpoint.submit_data(np.array([self.config['current_setpoint']], dtype='float32'))

        self.nd_setpoint.submit_data(np.array([self.config['nd_setpoint']], dtype='float32'))
        self.swp_setpoint.submit_data(np.array([self.config['swp_setpoint']], dtype='float32'))
        self.lwp_setpoint.submit_data(np.array([self.config['lwp_setpoint']], dtype='float32'))

        # Define thread functions.
        funcs = {
            'nd_setpoint': self.monitor_func(self.nd_setpoint, self.set_nd_setpoint),
            'swp_setpoint': self.monitor_func(self.swp_setpoint, self.set_swp_setpoint),
            'lwp_setpoint': self.monitor_func(self.lwp_setpoint, self.set_lwp_setpoint),
            'emission': self.monitor_func(self.emission, self.set_emission),
            'power_setpoint': self.monitor_func(self.power_setpoint, self.set_power_setpoint),
            'current_setpoint': self.monitor_func(self.current_setpoint, self.set_current_setpoint),
            'varia_status': self.watch_func(self.update_varia_status),
            'evo_status': self.watch_func(self.update_evo_status)
        }

        # Start all threads.
        for key, func in funcs.items():
            thread = threading.Thread(target=func)
            thread.start()

            self.threads[key] = thread

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        # Join all threads.
        for thread in self.threads.values():
            thread.join()

    def update_evo_status(self):
        self.base_temperature.submit_data(np.array([28.5], dtype='float32'))
        self.supply_voltage.submit_data(np.array([24.1], dtype='float32'))
        self.external_control_input.submit_data(np.array([4.2], dtype='float32'))

    def update_varia_status(self):
        # Submit bogus results to their respective datastreams.
        self.nd_filter_moving.submit_data(np.array([0], dtype='uint8'))
        self.swp_filter_moving.submit_data(np.array([0], dtype='uint8'))
        self.lwp_filter_moving.submit_data(np.array([0], dtype='uint8'))

        self.monitor_input.submit_data(np.array([1], dtype='float32'))

    def monitor_func(self, stream, setter):
        def func():
            while not self.should_shut_down:
                try:
                    frame = stream.get_next_frame(1)
                except Exception:
                    continue

                setter(frame.data[0])

        return func

    def update_func(self, updater):
        def func():
            while not self.should_shut_down:
                updater()

                self.sleep(1)

        return func

    def set_emission(self, emission):
        self.simulator.set_source_power(emission * self.power_setpoint.get()[0] * 1e-2)

    def set_power_setpoint(self, power_setpoint):
        self.simulator.set_source_power(self.emission.get()[0] * power_setpoint)

    def set_current_setpoint(self, current_setpoint):
        pass

    def set_nd_setpoint(self, nd_setpoint):
        self.simulator.move_filter(self.id + '_nd', nd_setpoint)

    def set_swp_setpoint(self, swp_setpoint):
        self.simulator.move_filter(self.id + '_swp', swp_setpoint)

    def set_lwp_setpoint(self, lwp_setpoint):
        self.simulator.move_filter(self.id + '_lwp', lwp_setpoint)


if __name__ == '__main__':
    service = NktSuperkSim()
    service.run()
