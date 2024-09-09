from catkit2.testbed.service import Service

import os
import ctypes

import numpy as np
import threading
from enum import Enum


class MCLS1_COM(Enum):
    BUFFER_SIZE = 255
    BAUD_RATE = 115200

    TERM_CHAR = "\r"
    GET_CURRENT = "current?"  # float (mA)
    SET_CURRENT = "current="
    GET_ENABLE = "enable?"  # bool/int
    SET_ENABLE = "enable="
    SET_SYSTEM = "system="
    GET_CHANNEL = "channel?"  # int
    SET_CHANNEL = "channel="
    GET_TARGET_TEMP = "target?"  # float (C)
    SET_TARGET_TEMP = "target="
    GET_TEMP = "temp?"  # float (C)
    GET_POWER = "power?"  # float (mW)
    GET_SYSTEM = "system?"  # bool

    # The following are untested.
    GET_COMMANDS = "?"
    GET_ID = "id?"
    GET_SPECS = "specs?"
    GET_STEP = "step?"
    SET_STEP = "step="
    SAVE = "save"
    GET_STATUS = "statword"


def make_setter(command):
    command_prefix = f"{command.value}"

    def setter(self, value):
        command_str = command_prefix + f"{value}{MCLS1_COM.TERM_CHAR.value}"

        # Lock first to ensure the next two statements are uninterrupted.
        with self.lock:
            # Set the channel.
            if command not in [MCLS1_COM.SET_CHANNEL, MCLS1_COM.SET_SYSTEM]:
                self.set_active_channel(self.channel)

            # Execute command.
            self.UART_lib.fnUART_LIBRARY_Set(self.instrument_handle, command_str.encode(), 32)

    return setter


def make_getter(command, stream_name):
    def getter(self):
        # Form command.
        command_str = command.value + MCLS1_COM.TERM_CHAR.value
        response_buffer = ctypes.create_string_buffer(MCLS1_COM.BUFFER_SIZE.value)

        # Lock first to ensure the next two statements are uninterrupted.
        with self.lock:
            # Set the channel.
            if command not in [MCLS1_COM.GET_CHANNEL]:
                self.set_active_channel(self.channel)

            # Execute command.
            self.UART_lib.fnUART_LIBRARY_Get(self.instrument_handle, command_str.encode(), response_buffer)

        # Decode result.
        response_buffer = response_buffer.value
        value = response_buffer.rstrip(b"\x00").decode().lstrip(command.value).strip('\r').rstrip('\r> ')

        # Submit retrieved value to stream.
        stream = getattr(self, stream_name)
        stream.submit_data(np.array([value]).astype(stream.dtype))

        return value

    return getter


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

        # Use a reentrant lock to avoid deadlock when setting the channel.
        self.lock = threading.RLock()

        try:
            uart_lib_path = os.environ.get('CATKIT_THORLABS_UART_LIB_PATH')
            self.UART_lib = ctypes.cdll.LoadLibrary(uart_lib_path)
        except ImportError as error:
            raise error

    def open(self):
        # Make datastreams
        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)
        self.emission = self.make_data_stream('emission', 'uint8', [1], 20)
        self.target_temperature = self.make_data_stream('target_temperature', 'float32', [1], 20)
        self.temperature = self.make_data_stream('temperature', 'float32', [1], 20)
        self.power = self.make_data_stream('power', 'float32', [1], 20)

        # Open connection to device
        response_buffer = ctypes.create_string_buffer(MCLS1_COM.BUFFER_SIZE.value)
        self.UART_lib.fnUART_LIBRARY_list(response_buffer, MCLS1_COM.BUFFER_SIZE.value)
        response_buffer = response_buffer.value.decode()
        split = response_buffer.split(",")

        for i, thing in enumerate(split):
            # The list has a format of "Port, Device, Port, Device". Once we find device named VCPO, minus 1 for port.
            if 'VCP0' in thing:
                self.port = split[i - 1]
                break
        else:
            raise Exception('Device VCP0 not found')

        self.instrument_handle = self.UART_lib.fnUART_LIBRARY_open(self.port.encode(), MCLS1_COM.BAUD_RATE.value, 3)

        self.setters = {
            'emission': self.set_emission,
            'current_setpoint': self.set_current_setpoint,
            'target_temperature': self.set_target_temperature
        }

        self.getters = [
            self.get_temperature,
            self.get_power
        ]

        # Start all monitoring threads.
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
        self.current_setpoint.submit_data(np.array([self.config['current_setpoint']], dtype='float32'))
        self.target_temperature.submit_data(np.array([self.config['target_temperature']], dtype='float32'))

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        # Turn off the source.
        self.set_emission(0)

        # Join all threads.
        for thread in self.threads.values():
            thread.join()

        # Close the instrument.
        self.UART_lib.fnUART_LIBRARY_close(self.instrument_handle)

    def update_status(self):
        while not self.should_shut_down:
            for getter in self.getters:
                getter()

            self.sleep(1)

    @property
    def channel(self):
        return self.config['channel']

    set_emission = make_setter(MCLS1_COM.SET_ENABLE)
    set_current_setpoint = make_setter(MCLS1_COM.SET_CURRENT)
    set_target_temperature = make_setter(MCLS1_COM.SET_TARGET_TEMP)
    set_active_channel = make_setter(MCLS1_COM.SET_CHANNEL)

    get_temperature = make_getter(MCLS1_COM.GET_TEMP, 'temperature')
    get_power = make_getter(MCLS1_COM.GET_POWER, 'power')


if __name__ == '__main__':
    service = ThorlabsMcls1()
    service.run()
