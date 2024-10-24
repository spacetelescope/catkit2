import numpy as np
import threading

from catkit2.testbed.service import Service


def make_monitor_func(stream, setter):
    def func(self):
        while not self.should_shut_down:
            try:
                frame = stream.get_next_frame(1)
            except Exception:
                continue

            setter(frame.data[0])

    return func


class ThorlabsMcls1Sim(Service):

    def __init__(self):
        super().__init__('thorlabs_mcls1_sim')
        self.threads = {}

    def open(self):
        # Make datastreams
        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)
        self.power_setpoint = self.make_data_stream('power_setpoint', 'float32', [1], 20)
        self.emission = self.make_data_stream('emission', 'uint8', [1], 20)
        self.target_temperature = self.make_data_stream('target_temperature', 'float32', [1], 20)
        self.temperature = self.make_data_stream('temperature', 'float32', [1], 20)
        self.power = self.make_data_stream('power', 'float32', [1], 20)

        self.setters = {
            'emission': self.set_emission,
            'current_setpoint': self.set_current_setpoint,
            'power_setpoint': self.set_power_setpoint,
            'target_temperature': self.set_target_temperature,
        }

        self.getters = [
            self.get_temperature,
            self.get_power
        ]

        for key, setter in self.setters.items():
            func = make_monitor_func(getattr(self, key), setter)
            thread = threading.Thread(target=func, args=(self,))
            thread.start()

            self.threads[key] = thread

        thread = threading.Thread(target=self.update_status)
        thread.start()
        self.threads['status'] = thread

        # Submit initial values
        self.emission.submit_data(np.array([int(self.config['emission'])], dtype='uint8'))
        self.power_setpoint.submit_data(np.array([self.config['power_setpoint']], dtype='float32'))
        self.current_setpoint.submit_data(np.array([self.config['current_setpoint']], dtype='float32'))
        self.target_temperature.submit_data(np.array([self.config['target_temperature']], dtype='float32'))

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        # Turn off the source
        self.set_emission(0)

        # Join all threads.
        for thread in self.threads.values():
            thread.join()

    def update_status(self):
        while not self.should_shut_down:
            for getter in self.getters:
                getter()

            self.sleep(1)

    def set_emission(self, emission):
        self.testbed.simulator.set_source_power(
            source_name=self.id,
            power=emission * self.power_setpoint.get()[0] * 1e-2
        )

    def set_power_setpoint(self, power_setpoint):
        self.testbed.simulator.set_source_power(
            source_name=self.id,
            power=self.emission.get()[0] * power_setpoint
        )

    def set_current_setpoint(self, value):
        pass

    def set_target_temperature(self, value):
        pass

    def get_power(self):
        return self.testbed.simulator.light_source_data[self.id + '_power']

    def get_temperature(self):
        return self.config['target_temperature']


if __name__ == '__main__':
    service = ThorlabsMcls1Sim()
    service.run()
