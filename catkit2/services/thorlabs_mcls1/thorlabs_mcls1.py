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

class MCLS1(Service):

    def __init__(self):
        super().__init__('mcls1')

        self.threads = {}
        self.port = self.config['port']

    def open(self):
        # Make datastreams
        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)
        self.emission = self.make_data_stream('enable', 'uint8', [1], 1)
        self.channel = self.make_data_stream('channel', 'uint8', [1], 20)
        self.target_temperature = self.make_data_stream('target_temperature', 'float32', [1], 20)
        self.temperature = self.make_data_stream('temperature', 'float32', [1], 20)
        self.power = self.make_data_stream('power', 'float32', [1], 20)

        self.monitor_input = self.make_data_stream('monitor_input', 'float32', [1], 20)

        self.emission.submit_data(np.array([self.config['emission']], dtype='uint8'))
        self.power_setpoint.submit_data(np.array([self.config['power_setpoint']], dtype='float32'))
        self.current_setpoint.submit_data(np.array([self.config['current_setpoint']], dtype='float32'))

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