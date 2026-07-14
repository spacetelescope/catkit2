from catkit2.testbed.service import Service

import numpy as np
import threading
from catkit2.services.thorlabs_mcls1.mcls1 import MCLS1


def make_monitor_func(stream, setter):
    def func(self):
        while not self.should_shut_down:
            try:
                frame = stream.get_next_frame(1)
            except Exception:
                continue

            setter(frame.data[0])

    return func


class ThorlabsMcls1(Service):
    def __init__(self):
        super().__init__('thorlabs_mcls1')

        self.threads = {}
        self.instrument_handle = None
        self.serial_handle = None
        self.UART_lib = None

        self.vcp_port = self.config.get('vcp_port', None)
        self.serial_port = self.config.get('serial_port', None)
        self.serial_timeout = self.config.get('serial_timeout', None)
        self.baud_rate = MCLS1_COM.BAUD_RATE.value

        self.backend = self._select_backend()

        # Use a reentrant lock to avoid deadlock when setting the channel.
        self.lock = threading.RLock()

    def open(self):
        # Make datastreams
        self.current_setpoint_stream = self.make_data_stream('current_setpoint', 'float32', [1], 20)
        self.emission_stream = self.make_data_stream('emission', 'uint8', [1], 20)
        self.target_temperature_stream = self.make_data_stream('target_temperature', 'float32', [1], 20)
        self.temperature_stream = self.make_data_stream('temperature', 'float32', [1], 20)
        self.power_stream = self.make_data_stream('power', 'float32', [1], 20)

        # Open connection to device
        self.port = self.config['port']
        self.instrument = MCLS1(self.port)
        self.instrument.open()

        def make_property_helper(name, read_only=False):
            if read_only:
                self.make_property(name, lambda: getattr(self, name))
            else:
                def setter(val):
                    setattr(self, name, val)
                self.make_property(name, lambda: getattr(self, name), setter)

        make_property_helper('channel')
        make_property_helper('emission')
        make_property_helper('current_setpoint')
        make_property_helper('target_temperature')
        make_property_helper('temperature', read_only=True)
        make_property_helper('power', read_only=True)

        self.setters = {
            'emission': self._set_emission,
            'current_setpoint': self._set_current_setpoint,
            'target_temperature': self._set_target_temperature
        }

        self.getters = [
            self.get_temperature,
            self.get_power
        ]

        # Start all monitoring threads.
        for key, setter in self.setters.items():
            func = make_monitor_func(getattr(self, key + '_stream'), setter)

            thread = threading.Thread(target=func, args=(self,))
            thread.start()

            self.threads[key] = thread

        #thread = threading.Thread(target=self.update_status)
        #thread.start()

        self.threads['status'] = thread

        # Submit initial values
        self.emission_stream.submit_data(np.array([int(self.config['emission'])], dtype='uint8'))
        self.current_setpoint_stream.submit_data(np.array([self.config['current_setpoint']], dtype='float32'))
        self.target_temperature_stream.submit_data(np.array([self.config['target_temperature']], dtype='float32'))

    def main(self):
        while not self.should_shut_down:
            self.sleep(.1)

    def close(self):
        # Join all threads.
        for thread in self.threads.values():
            thread.join()

        # Close the instrument.
        self.instrument.close()

    def update_status(self):
        while not self.should_shut_down:
            for getter in self.getters:
                getter()

            self.sleep(.5)

    @property
    def channel(self):
        return self.config['channel']

    @property
    def emission(self):
        with self.lock:
            return self.instrument.get_enable(self.channel)

    @emission.setter
    def emission(self, value):
        self._set_emission(value)

    def _set_emission(self, value):
        with self.lock:
            self.instrument.set_enable(self.channel, bool(value))
            if bool(value):
                self.instrument.system_enable(True)

    @property
    def current_setpoint(self):
        with self.lock:
            return self.instrument.get_current(self.channel)

    @current_setpoint.setter
    def current_setpoint(self, value):
        self._set_current_setpoint(value)

    def _set_current_setpoint(self, value):
        with self.lock:
            self.instrument.set_current(self.channel, float(value))

    @property
    def target_temperature(self):
        with self.lock:
            return self.instrument.get_target(self.channel)

    @target_temperature.setter
    def target_temperature(self, value):
        self._set_target_temperature(value)

    def _set_target_temperature(self, value):
        with self.lock:
            self.instrument.set_target(self.channel, float(value))

    def get_temperature(self):
        with self.lock:
            value = self.instrument.temperature(self.channel)
        print(f"temperature = {value}")
        self.temperature_stream.submit_data(np.array([value]).astype(self.temperature_stream.dtype))
        return value

    @property
    def temperature(self):
        return self.get_temperature()

    def get_power(self):
        with self.lock:
            value = self.instrument.power(self.channel)
        print(f"power = {value}")
        self.power_stream.submit_data(np.array([value]).astype(self.power_stream.dtype))
        return value

    @property
    def power(self):
        return self.get_power()


if __name__ == '__main__':
    service = ThorlabsMcls1()
    service.run()
