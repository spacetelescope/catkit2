from catkit2.testbed.service import Service

import os
import ctypes

import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading
from enum import Enum
import sys


try:
    uart_lib_path = os.path.join(os.environ.get('CATKIT_THORLABS_UART_LIB_PATH'))
    UART_lib = ctypes.cdll.LoadLibrary(uart_lib_path)
except ImportError as error:
    raise error


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

class ThorlabsMcls1(Service):

    def __init__(self):
        super().__init__('thorlabs_mcls1')

        self.threads = {}
        self.port = self.config['port']

    def open(self):
        # Make datastreams
        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)
        self.emission = self.make_data_stream('emission', 'uint8', [1], 1)
        self.channel = self.make_data_stream('channel', 'uint8', [1], 20)
        self.target_temperature = self.make_data_stream('target_temperature', 'float32', [1], 20)
        self.temperature = self.make_data_stream('temperature', 'float32', [1], 20)
        self.power = self.make_data_stream('power', 'float32', [1], 20)

        self.emission.submit_data(np.array([int(self.config['emission'])], dtype='uint8'))
        self.current_setpoint.submit_data(np.array([self.config['current_setpoint']], dtype='float32'))
        self.channel.submit_data(np.array([self.config['channel']], dtype='uint8'))

        response_buffer = ctypes.create_string_buffer(MCLS1_COM.BUFFER_SIZE.value)
        UART_lib.fnUART_LIBRARY_list(response_buffer, MCLS1_COM.BUFFER_SIZE.value)
        response_buffer = response_buffer.value.decode()
        split = response_buffer.split(",")
        for i, thing in enumerate(split):
            # The list has a format of "Port, Device, Port, Device". Once we find device named VCPO, minus 1 for port.
            if self.device_id in thing:
                self.port = split[i - 1]

        self.instrument_handle = UART_lib.fnUART_LIBRARY_open(self.port.encode(), MCLS1_COM.BAUD_RATE.value, 3)

        self.setters = {
            'emission': self.create_setter(MCLS1_COM.SET_ENABLE),
            'current_setpoint': self.create_setter(MCLS1_COM.SET_CURRENT),
            'channel': self.create_setter(MCLS1_COM.SET_CHANNEL),
            'target_temperature': self.create_setter(MCLS1_COM.SET_TARGET_TEMP),
        }

        funcs = {
            'emission': self.monitor_func(self.emission, self.create_setter(MCLS1_COM.SET_ENABLE)),
            'current_setpoint': self.monitor_func(self.current_setpoint, self.create_setter(MCLS1_COM.SET_CURRENT)),
            'channel': self.monitor_func(self.channel, self.create_setter(MCLS1_COM.SET_CHANNEL)),
            'target_temperature': self.monitor_func(self.target_temperature,
                                                    self.create_setter(MCLS1_COM.SET_TARGET_TEMP)),
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
        # Turn off the source
        self.set_emission(0)

        # Join all threads.
        for thread in self.threads.values():
            thread.join()

    def create_setter(self, command):
        command_prefix = f"{command.value}"
        def setter(value):
            command_str = command_prefix + f"{value}{MCLS1_COM.TERM_CHAR.value}"
            UART_lib.fnUART_LIBRARY_Set(self.instrument_handle, command_str.encode(), 32)

        return setter

    def create_getter(self, command):
        command_prefix = f"{command.value}"

        def getter():
            command_str = command.value + MCLS1_COM.TERM_CHAR.value
            response_buffer = ctypes.create_string_buffer(MCLS1_COM.BUFFER_SIZE.value)
            UART_lib.fnUART_LIBRARY_Get(self.instrument_handle, command.encode(), response_buffer)
            response_buffer = response_buffer.value
            return response_buffer.rstrip(b"\x00").decode()

        return getter

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


if __name__ == '__main__':
    service = ThorlabsMcls1()
    service.run()
