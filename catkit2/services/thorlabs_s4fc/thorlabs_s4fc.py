from catkit2.testbed.service import Service

import ctypes
import os
import platform
import threading
from enum import Enum

import numpy as np


class S4FC_COM(Enum):
    BUFFER_SIZE = 255
    BAUD_RATE = 115200

    TERM_CHAR = "\r"
    # Command strings from S4FC manual section 5.11.
    GET_POWER_SETPOINT = "LD OUTPUT SETPOINT?"  # float (mW when configured for power control)
    SET_POWER_SETPOINT = "LD OUTPUT SETPOINT="
    GET_ENABLE = "ENABLE?"  # bool/int
    SET_ENABLE = "ENABLE="
    GET_TARGET_TEMP = "TEMP SET POINT?"  # float (C)
    SET_TARGET_TEMP = "TEMP SET POINT="
    GET_TEMP = "LASER TEMP?"  # float (C)
    GET_POWER = "LD ACTUAL OUTPUT?"  # float (device LD output units)
    GET_LASER_LOCK = "LOCK?"
    SET_LASER_LOCK = "LOCK="

def make_setter(command):
    command_prefix = command.value

    def setter(self, value):
        command_str = f"{command_prefix}{value}{S4FC_COM.TERM_CHAR.value}"

        with self.lock:
            self._set_command(command_str)

    return setter


def make_getter(command, stream_name):
    def getter(self):
        command_str = command.value + S4FC_COM.TERM_CHAR.value

        with self.lock:
            response = self._get_command(command_str)

        value = self._parse_response_value(response)

        stream = getattr(self, stream_name)
        try:
            stream.submit_data(np.array([value]).astype(stream.dtype))
        except ValueError as exc:
            raise ValueError('Error likely due to incorrect Port after a reboot') from exc

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


class ThorlabsS4fc(Service):
    def __init__(self):
        super().__init__('thorlabs_s4fc')

        self.threads = {}
        self.instrument_handle = None
        self.serial_handle = None
        self.UART_lib = None

        self.port = self.config.get('port', None)
        self.serial_port = self.config.get('serial_port', None)
        self.serial_timeout = self.config.get('serial_timeout', None)
        self.baud_rate = self.config.get('baud_rate', S4FC_COM.BAUD_RATE.value)
        self.initial_power_setpoint = self.config.get('power_setpoint', None)

        if self.initial_power_setpoint is None:
            raise RuntimeError('Missing required config key: power_setpoint (mW)')

        self.backend = self._select_backend()
        self.lock = threading.RLock()

        if self.backend == 'uart_lib':
            uart_lib_path = os.environ.get('CATKIT_THORLABS_S4FC_UART_LIB_PATH')
            if not uart_lib_path:
                raise RuntimeError('CATKIT_THORLABS_S4FC_UART_LIB_PATH is not set for the Windows UART-library backend')
            self.UART_lib = ctypes.cdll.LoadLibrary(uart_lib_path)
            self._configure_uart_lib_api()

    def _configure_uart_lib_api(self):
        """Configure the ctypes signatures to match the Thorlabs SDK."""
        lib = self.UART_lib

        for func_name, argtypes in {
            'common_List': [ctypes.c_void_p],
            'common_Open': [ctypes.c_char_p, ctypes.c_int, ctypes.c_int],
            'common_Close': [ctypes.c_int],
            'GetHandle': [ctypes.c_char_p],
        }.items():
            if hasattr(lib, func_name):
                getattr(lib, func_name).argtypes = argtypes
                getattr(lib, func_name).restype = ctypes.c_int

        for func_name, argtypes in {
            's4fc_GetEnable': [ctypes.c_int, ctypes.POINTER(ctypes.c_bool)],
            's4fc_GetLock': [ctypes.c_int, ctypes.POINTER(ctypes.c_bool)],
            's4fc_GetActualPower': [ctypes.c_int, ctypes.POINTER(ctypes.c_double)],
            's4fc_GetLaserTemp': [ctypes.c_int, ctypes.POINTER(ctypes.c_double)],
            's4fc_GetTempSetPoint': [ctypes.c_int, ctypes.POINTER(ctypes.c_double)],
            's4fc_SetTempSetPoint': [ctypes.c_int, ctypes.c_double],
            's4fc_SetLDOutputSetPoint': [ctypes.c_int, ctypes.c_double],
            's4fc_SetEnable': [ctypes.c_int, ctypes.c_bool],
            's4fc_SetLock': [ctypes.c_int, ctypes.c_bool],
            's4fc_SetAdjustCurrentNotmW': [ctypes.c_int, ctypes.c_bool],
        }.items():
            if hasattr(lib, func_name):
                getattr(lib, func_name).argtypes = argtypes
                getattr(lib, func_name).restype = ctypes.c_int

    def _select_backend(self):
        if platform.system().lower().startswith('win'):
            return 'uart_lib'
        return 'serial'

    def _connect(self):
        if self.backend == 'uart_lib':
            self._connect_uart_lib()
        elif self.backend == 'serial':
            self._connect_serial()
        else:
            raise RuntimeError(f'Unsupported backend: {self.backend}')

    def _disconnect(self):
        if self.backend == 'uart_lib' and self.instrument_handle is not None:
            try:
                self.UART_lib.common_Close(self.instrument_handle)
            except TypeError:
                pass
            self.instrument_handle = None
        elif self.backend == 'serial' and self.serial_handle is not None:
            self.serial_handle.close()
            self.serial_handle = None

    def _connect_uart_lib(self):
        response_buffer = ctypes.create_string_buffer(4096)
        try:
            self.UART_lib.common_List(response_buffer)
        except TypeError:
            self.UART_lib.common_List(ctypes.cast(response_buffer, ctypes.c_void_p))
        devices = response_buffer.value.decode(errors='ignore')
        split = [item.strip() for item in devices.replace('\0', '').split(',') if item.strip()]

        selected_port = None
        if self.port:
            for index, item in enumerate(split):
                if self.port in item and index > 0:
                    selected_port = split[index - 1]
                    break

        if selected_port is None:
            if self.serial_port:
                selected_port = self.serial_port
            elif split:
                selected_port = split[0]

        if selected_port is None:
            raise RuntimeError('No UART devices found for Thorlabs S4FC FP source')

        try:
            self.instrument_handle = self.UART_lib.common_Open(selected_port.encode(), self.baud_rate, 3)
        except TypeError:
            self.instrument_handle = self.UART_lib.GetHandle(selected_port.encode())

    def _connect_serial(self):
        serial_module = self._require_pyserial()
        self.serial_handle = serial_module.Serial(
            port=self.serial_port,
            baudrate=self.baud_rate,
            timeout=self.serial_timeout,
            write_timeout=self.serial_timeout,
        )
        self.serial_handle.reset_input_buffer()
        self.serial_handle.reset_output_buffer()


    def _set_command(self, command_str):
        payload = command_str.encode()
        if self.backend == 'uart_lib':
            if command_str.startswith('ENABLE='):
                value = int(command_str[len('ENABLE='):].rstrip('\r'))
                self.UART_lib.s4fc_SetEnable(self.instrument_handle, bool(value))
            elif command_str.startswith('LOCK='):
                value = int(command_str[len('LOCK='):].rstrip('\r'))
                self.UART_lib.s4fc_SetLock(self.instrument_handle, bool(value))
            elif command_str.startswith('TEMP SET POINT='):
                value = float(command_str[len('TEMP SET POINT='):].rstrip('\r'))
                self.UART_lib.s4fc_SetTempSetPoint(self.instrument_handle, value)
            elif command_str.startswith('LD OUTPUT SETPOINT='):
                value = float(command_str[len('LD OUTPUT SETPOINT='):].rstrip('\r'))
                self.UART_lib.s4fc_SetLock(self.instrument_handle, False)
                self.UART_lib.s4fc_SetAdjustCurrentNotmW(self.instrument_handle, False)
                self.UART_lib.s4fc_SetLDOutputSetPoint(self.instrument_handle, value)
                self.UART_lib.s4fc_SetLock(self.instrument_handle, True)
            else:
                raise RuntimeError(f'Unsupported S4FC UART command: {command_str!r}')
        elif self.backend == 'serial':
            self.serial_handle.write(payload)
            self.serial_handle.flush()

    def _get_command(self, command_str):
        if self.backend == 'uart_lib':
            if command_str.startswith('ENABLE?'):
                value = ctypes.c_bool()
                self.UART_lib.s4fc_GetEnable(self.instrument_handle, ctypes.byref(value))
                return str(int(value.value)).encode()
            if command_str.startswith('LOCK?'):
                value = ctypes.c_bool()
                self.UART_lib.s4fc_GetLock(self.instrument_handle, ctypes.byref(value))
                return str(int(value.value)).encode()
            if command_str.startswith('TEMP SET POINT?'):
                value = ctypes.c_double()
                self.UART_lib.s4fc_GetTempSetPoint(self.instrument_handle, ctypes.byref(value))
                return str(value.value).encode()
            if command_str.startswith('LASER TEMP?'):
                value = ctypes.c_double()
                self.UART_lib.s4fc_GetLaserTemp(self.instrument_handle, ctypes.byref(value))
                return str(value.value).encode()
            if command_str.startswith('LD ACTUAL OUTPUT?'):
                value = ctypes.c_double()
                self.UART_lib.s4fc_GetActualPower(self.instrument_handle, ctypes.byref(value))
                return str(value.value).encode()
            raise RuntimeError(f'Unsupported S4FC UART query: {command_str!r}')

        payload = command_str.encode()
        self.serial_handle.reset_input_buffer()
        self.serial_handle.write(payload)
        self.serial_handle.flush()
        return self.serial_handle.read_until(b'>')

    @staticmethod
    def _parse_response_value(response):
        text = response.rstrip(b'\x00').decode(errors='ignore')

        lines = [
            line.strip(' \r\n\t> <')
            for line in text.splitlines()
            if line.strip(' \r\n\t> <')
        ]

        if not lines:
            raise ValueError(f'Empty serial response: {text!r}')

        return lines[-1]

    def open(self):
        self.power_setpoint = self.make_data_stream('power_setpoint', 'float32', [1], 20)
        self.emission = self.make_data_stream('emission', 'uint8', [1], 20)
        self.target_temperature = self.make_data_stream('target_temperature', 'float32', [1], 20)
        self.temperature = self.make_data_stream('temperature', 'float32', [1], 20)
        self.laser_lock = self.make_data_stream('laser_lock', 'uint8', [1], 20)

        self._connect()

        self.make_command('get_enable', self.get_enable)

        self.setters = {
            'emission': self.set_emission,
            'power_setpoint': self.set_power_setpoint,
            'target_temperature': self.set_target_temperature,
            'laser_lock': self.set_laser_lock,
        }

        self.getters = [
            self.get_temperature,
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

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        self.set_emission(0)

        for thread in self.threads.values():
            thread.join()

        self._disconnect()

    def update_status(self):
        while not self.should_shut_down:
            for getter in self.getters:
                getter()

            self.sleep(1)

    def get_enable(self):
        """Read the hardware enable state, independently of the emission command stream."""
        command_str = S4FC_COM.GET_ENABLE.value + S4FC_COM.TERM_CHAR.value

        with self.lock:
            response = self._get_command(command_str)

        return bool(int(float(self._parse_response_value(response))))

    set_emission = make_setter(S4FC_COM.SET_ENABLE)
    set_power_setpoint = make_setter(S4FC_COM.SET_POWER_SETPOINT)
    set_laser_lock = make_setter(S4FC_COM.SET_LASER_LOCK)

    # Backward-compatible alias for older callers.
    set_target_temperature = make_setter(S4FC_COM.SET_TARGET_TEMP)

    get_temperature = make_getter(S4FC_COM.GET_TEMP, 'temperature')
    get_power_setpoint = make_getter(S4FC_COM.GET_POWER, 'power')


if __name__ == '__main__':
    service = ThorlabsS4fc()
    service.run()
