import time

from catkit2.testbed.service import Service

import os
import ctypes
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import threading
from enum import Enum


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


    def open(self):
        # Make datastreams
        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)
        self.emission = self.make_data_stream('emission', 'uint8', [1], 1)
        self.target_temperature = self.make_data_stream('target_temperature', 'float32', [1], 20)
        self.temperature = self.make_data_stream('temperature', 'float32', [1], 20)
        self.power = self.make_data_stream('power', 'float32', [1], 20)

        self.emission.submit_data(np.array([int(self.config['emission'])], dtype='uint8'))
        self.current_setpoint.submit_data(np.array([self.config['current_setpoint']], dtype='float32'))

        response_buffer = ctypes.create_string_buffer(MCLS1_COM.BUFFER_SIZE.value)
        UART_lib.fnUART_LIBRARY_list(response_buffer, MCLS1_COM.BUFFER_SIZE.value)
        response_buffer = response_buffer.value.decode()
        split = response_buffer.split(",")
        for i, thing in enumerate(split):
            # The list has a format of "Port, Device, Port, Device". Once we find device named VCPO, minus 1 for port.
            if 'VCP0' in thing:
                self.port = split[i - 1]
                break
        else:
            raise Exception('Device VCP0 not found')

        self.instrument_handle = UART_lib.fnUART_LIBRARY_open(self.port.encode(), MCLS1_COM.BAUD_RATE.value, 3)

        # Create a pool with a single worker to perform communication with the device.
        self.pool = ThreadPoolExecutor(max_workers=1)

        self.setters = {
            'emission': self.create_setter(MCLS1_COM.SET_ENABLE),
            'current_setpoint': self.create_setter(MCLS1_COM.SET_CURRENT),
            'target_temperature': self.create_setter(MCLS1_COM.SET_TARGET_TEMP),
        }

        self.status_funcs = {
            'temperature': (self.temperature, self.create_getter(MCLS1_COM.GET_TEMP)),
            'power': (self.power, self.create_getter(MCLS1_COM.GET_POWER))
        }

        funcs = {
            'emission': self.monitor_func(self.emission, self.setters['emission']),
            'current_setpoint': self.monitor_func(self.current_setpoint, self.setters['current_setpoint']),
            'target_temperature': self.monitor_func(self.target_temperature, self.setters['target_temperature']),
        }

        # Start all threads.
        for key, func in funcs.items():
            thread = threading.Thread(target=func)
            thread.start()

            self.threads[key] = thread

        thread = threading.Thread(target=self.update_status)
        thread.start()
        self.threads['status'] = thread

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        # Turn off the source
        self.setters['emission'](0)

        # Join all threads.
        for thread in self.threads.values():
            thread.join()

        self.pool.shutdown()
        UART_lib.fnUART_LIBRARY_close(self.instrument_handle)


    def create_setter(self, command):
        command_prefix = f"{command.value}"
        def setter(value):
            command_str = command_prefix + f"{value}{MCLS1_COM.TERM_CHAR.value}"
            UART_lib.fnUART_LIBRARY_Set(self.instrument_handle, command_str.encode(), 32)

        return setter

    def create_getter(self, command):
        def getter():
            command_str = command.value + MCLS1_COM.TERM_CHAR.value
            response_buffer = ctypes.create_string_buffer(MCLS1_COM.BUFFER_SIZE.value)
            UART_lib.fnUART_LIBRARY_Get(self.instrument_handle, command_str.encode(), response_buffer)
            response_buffer = response_buffer.value
            return response_buffer.rstrip(b"\x00").decode().lstrip(command.value).strip('\r').rstrip('\r> ')

        return getter

    def monitor_func(self, stream, setter):
        def func():
            while not self.should_shut_down:
                try:
                    frame = stream.get_next_frame(1)
                except Exception:
                    continue
                future = self.pool.submit(setter, frame.data[0])
                result = future.result()

        return func

    def update_status(self):
        while not self.should_shut_down:

            for stream, getter in self.status_funcs.values():
                future = self.pool.submit(getter)
                result, value = future.result()

                try:
                    stream.submit_data(np.array([value]).astype(stream.dtype))
                except Exception as e:
                    print(e)
            time.sleep(1)


if __name__ == '__main__':
    service = ThorlabsMcls1()
    service.run()
