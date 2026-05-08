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
            self._set_command(command_str)

    return setter


def make_getter(command, stream_name):
    def getter(self):
        # Form command.
        command_str = command.value + MCLS1_COM.TERM_CHAR.value

        # Lock first to ensure the next two statements are uninterrupted.
        with self.lock:
            # Set the channel.
            if command not in [MCLS1_COM.GET_CHANNEL]:
                self.set_active_channel(self.channel)

            # Execute command.
            response = self._get_command(command_str)

        # Decode result.
        value = self._parse_response_value(response, command.value)

        # Submit retrieved value to stream.
        stream = getattr(self, stream_name)
        try:
            stream.submit_data(np.array([value]).astype(stream.dtype))
        except ValueError:
            raise ValueError('Error likely due to incorrect COM/VCP port after a reboot')

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
        self.instrument_handle = None
        self.serial_handle = None
        self.UART_lib = None

        self.transport = self.config.get('transport', 'auto').lower()
        self.vcp_port = self.config.get('vcp_port', 'VCP0')
        self.serial_port = self.config.get('serial_port', self.config.get('port'))
        self.serial_timeout = float(self.config.get('serial_timeout', 1.0))
        self.baud_rate = int(self.config.get('baud_rate', MCLS1_COM.BAUD_RATE.value))

        self.backend = self._select_backend()

        # Use a reentrant lock to avoid deadlock when setting the channel.
        self.lock = threading.RLock()

        if self.backend == 'uart_lib':
            uart_lib_path = os.environ.get('CATKIT_THORLABS_UART_LIB_PATH')
            if not uart_lib_path:
                raise RuntimeError('CATKIT_THORLABS_UART_LIB_PATH is not set for UART-library transport')
            self.UART_lib = ctypes.cdll.LoadLibrary(uart_lib_path)

    def _select_backend(self):
        if self.transport in ('uart_lib', 'serial'):
            return self.transport

        if self.serial_port:
            return 'serial'

        # Default to UART library for backward compatibility with existing Windows configs.
        return 'uart_lib'

    def _connect(self):
        if self.backend == 'uart_lib':
            self._connect_uart_lib()
        elif self.backend == 'serial':
            self._connect_serial()
        else:
            raise RuntimeError(f'Unsupported transport backend: {self.backend}')

    def _disconnect(self):
        if self.backend == 'uart_lib' and self.instrument_handle is not None:
            self.UART_lib.fnUART_LIBRARY_close(self.instrument_handle)
            self.instrument_handle = None
        elif self.backend == 'serial' and self.serial_handle is not None:
            self.serial_handle.close()
            self.serial_handle = None

    def _connect_uart_lib(self):
        response_buffer = ctypes.create_string_buffer(MCLS1_COM.BUFFER_SIZE.value)
        self.UART_lib.fnUART_LIBRARY_list(response_buffer, MCLS1_COM.BUFFER_SIZE.value)
        devices = response_buffer.value.decode(errors='ignore')
        split = [item.strip() for item in devices.split(',') if item.strip()]

        selected_port = None
        for i, thing in enumerate(split):
            if self.vcp_port in thing and i > 0:
                selected_port = split[i - 1]
                break

        if selected_port is None:
            raise RuntimeError(
                f'Device {self.vcp_port} not found - MCLS1 may have switched COM/VCP port after a reboot'
            )

        self.port = selected_port
        self.instrument_handle = self.UART_lib.fnUART_LIBRARY_open(self.port.encode(), self.baud_rate, 3)

    def _resolve_serial_port(self):
        _, list_ports_module = self._require_pyserial()

        if self.serial_port:
            return self.serial_port

        ports = list_ports_module.comports()
        for port in ports:
            description = port.description or ''
            if self.vcp_port in description or self.vcp_port in port.device:
                return port.device

        raise RuntimeError(f'Unable to find serial port matching {self.vcp_port}')

    def _connect_serial(self):
        serial_module, _ = self._require_pyserial()
        self.port = self._resolve_serial_port()
        self.serial_handle = serial_module.Serial(
            port=self.port,
            baudrate=self.baud_rate,
            timeout=self.serial_timeout,
            write_timeout=self.serial_timeout,
        )
        self.serial_handle.reset_input_buffer()
        self.serial_handle.reset_output_buffer()

    @staticmethod
    def _require_pyserial():
        try:
            import serial as serial_module
            from serial.tools import list_ports as list_ports_module
        except ImportError as exc:
            raise RuntimeError('pyserial is required for serial transport but is not installed') from exc

        return serial_module, list_ports_module

    def _set_command(self, command_str):
        payload = command_str.encode()
        if self.backend == 'uart_lib':
            self.UART_lib.fnUART_LIBRARY_Set(self.instrument_handle, payload, len(payload))
            return

        self.serial_handle.write(payload)
        self.serial_handle.flush()

    def _get_command(self, command_str):
        payload = command_str.encode()
        if self.backend == 'uart_lib':
            response_buffer = ctypes.create_string_buffer(MCLS1_COM.BUFFER_SIZE.value)
            self.UART_lib.fnUART_LIBRARY_Get(self.instrument_handle, payload, response_buffer)
            return response_buffer.value

        self.serial_handle.reset_input_buffer()
        self.serial_handle.write(payload)
        self.serial_handle.flush()
        return self.serial_handle.read_until(b'>')

    @staticmethod
    def _parse_response_value(response, command):
        text = response.rstrip(b"\x00").decode(errors='ignore').strip('\r\n\t >')
        candidates = [
            command,
            command.rstrip('?'),
            f"{command.rstrip('?')}=",
        ]

        for candidate in candidates:
            if candidate and text.startswith(candidate):
                text = text[len(candidate):].lstrip('= ')
                break

        return text.strip('\r\n\t >')

    def open(self):
        # Make datastreams
        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)
        self.emission = self.make_data_stream('emission', 'uint8', [1], 20)
        self.target_temperature = self.make_data_stream('target_temperature', 'float32', [1], 20)
        self.temperature = self.make_data_stream('temperature', 'float32', [1], 20)
        self.power = self.make_data_stream('power', 'float32', [1], 20)

        # Open connection to device.
        self._connect()

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
        self._disconnect()

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
