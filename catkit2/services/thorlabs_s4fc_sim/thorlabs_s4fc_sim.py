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


class ThorlabsS4fcSim(Service):
    def __init__(self):
        super().__init__('thorlabs_s4fc_sim')
        self.threads = {}
        # Keep compatibility with older configs while standardizing the key to power_setpoint (mW).
        self.initial_power_setpoint = self.config.get('power_setpoint', self.config.get('current_setpoint', None))

        if self.initial_power_setpoint is None:
            raise RuntimeError('Missing required config key: power_setpoint (mW)')

    def open(self):
        self.power_setpoint = self.make_data_stream('power_setpoint', 'float32', [1], 20)
        self.emission = self.make_data_stream('emission', 'uint8', [1], 20)
        self.target_temperature = self.make_data_stream('target_temperature', 'float32', [1], 20)
        self.temperature = self.make_data_stream('temperature', 'float32', [1], 20)
        self.power = self.make_data_stream('power', 'float32', [1], 20)

        self.setters = {
            'emission': self.set_emission,
            'power_setpoint': self.set_power_setpoint,
            'target_temperature': self.set_target_temperature,
        }

        self.getters = [
            self.get_temperature,
            self.get_power,
        ]

        for key, setter in self.setters.items():
            func = make_monitor_func(getattr(self, key), setter)
            thread = threading.Thread(target=func, args=(self,))
            thread.start()
            self.threads[key] = thread

        thread = threading.Thread(target=self.update_status)
        thread.start()
        self.threads['status'] = thread

        self.emission.submit_data(np.array([int(self.config['emission'])], dtype='uint8'))
        self.power_setpoint.submit_data(np.array([self.initial_power_setpoint], dtype='float32'))
        self.target_temperature.submit_data(np.array([self.config['target_temperature']], dtype='float32'))
        self._publish_sim_power(self.emission.get()[0], self.power_setpoint.get()[0])

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        self.set_emission(0)

        for thread in self.threads.values():
            thread.join()

    def update_status(self):
        while not self.should_shut_down:
            for getter in self.getters:
                getter()

            self.sleep(1)

    def _publish_sim_power(self, emission, power_setpoint):
        power = emission * power_setpoint
        self.testbed.simulator.set_source_power(source_name=self.id, power=power)

    def set_emission(self, emission):
        self._publish_sim_power(emission, self.power_setpoint.get()[0])

    def set_power_setpoint(self, power_setpoint):
        self._publish_sim_power(self.emission.get()[0], power_setpoint)

    # Backward-compatible alias for older callers.
    set_current_setpoint = set_power_setpoint

    def set_target_temperature(self, value):
        pass

    def get_power(self):
        return self.testbed.simulator.light_source_data[self.id + '_power']

    def get_temperature(self):
        return self.config['target_temperature']


if __name__ == '__main__':
    service = ThorlabsS4fcSim()
    service.run()
