from catkit2.testbed.service import Service

import numpy as np
import threading


class NktSuperkFianiumSim(Service):
    def __init__(self):
        super().__init__('nkt_superk_fianium_sim')

        self.threads = {}
        self.port = self.config['port']

    def open(self):
        # Make datastreams.
        self.emission = self.make_data_stream('emission', 'uint8', [1], 20)
        self.power_setpoint = self.make_data_stream('power_setpoint', 'float32', [1], 20)
        self.pulse_picker_ratio = self.make_data_stream('pulse_picker_ratio', 'uint16', [1], 20)

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
        self.pulse_picker_ratio.submit_data(np.array([self.config['pulse_picker_ratio']], dtype='uint16'))

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
            'pulse_picker_ratio': self.monitor_pulse_picker_ratio(self.pulse_picker_ratio, self.set_pulse_picker_ratio),
            'varia_status': self.update_func(self.update_varia_status)
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
        # Stop emission
        self.set_emission(0)
        # Join all threads.
        for thread in self.threads.values():
            thread.join()

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

    def monitor_pulse_picker_ratio(self, stream, setter):
        def func():
            while not self.should_shut_down:
                try:
                    frame = stream.get_next_frame(1)
                except Exception:
                    continue

                bandwidth = self.swp_setpoint.get()[0] - self.lwp_setpoint.get()[0]
                if frame.data[0] >= max(int(bandwidth / self.pulse_picker_safety), 1):
                    setter(frame.data[0])
                else:
                    self.log.warning(f'Pulse picker ratio {frame.data[0]} is too low for the current bandwidth {bandwidth}. Not setting it.')

        return func

    def update_func(self, updater):
        def func():
            while not self.should_shut_down:
                updater()

                self.sleep(1)

        return func

    def set_emission(self, emission):
        self.testbed.simulator.set_source_power(
            source_name=self.id,
            power=emission * self.power_setpoint.get()[0] * 1e-2
        )

    def set_power_setpoint(self, power_setpoint):
        self.testbed.simulator.set_source_power(
            source_name=self.id,
            power=self.emission.get()[0] * power_setpoint * 1e-2
        )

    def set_pulse_picker_ratio(self, pulse_picker_ratio):
        # TODO: Something with the testbed simulator, likely set_source_power().
        pass

    def set_nd_setpoint(self, nd_setpoint):
        self.testbed.simulator.move_filter(
            filter_wheel_name=self.id + '_nd',
            new_filter_position=nd_setpoint
        )

    def set_swp_setpoint(self, swp_setpoint):
        self.testbed.simulator.move_filter(
            filter_wheel_name=self.id + '_swp',
            new_filter_position=swp_setpoint
        )

    def set_lwp_setpoint(self, lwp_setpoint):
        self.testbed.simulator.move_filter(
            filter_wheel_name=self.id + '_lwp',
            new_filter_position=lwp_setpoint
        )


if __name__ == '__main__':
    service = NktSuperkFianiumSim()
    service.run()
