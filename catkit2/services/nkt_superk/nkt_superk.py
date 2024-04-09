from catkit2.testbed.service import Service

import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading
from enum import Enum
import os
import sys


try:
    sdk_path = os.path.join(os.environ.get('NKTP_SDK_PATH'), 'Examples', 'DLL_Example_Python')
    if sdk_path is not None:
        sys.path.append(sdk_path)

    from NKTP_DLL import *
except ImportError:
    print('To use NKT SDK, you need to install the SDK and check the NKTP_SDK_PATH environment variable.')
    raise


# SuperK EVO registers.
class Evo(Enum):
    DEVICE_ID = 15

    REG_BASE_TEMPERATURE = 0x17
    REG_SUPPLY_VOLTAGE = 0x1D
    REG_EXTERNAL_CONTROL_INPUT = 0x94

    REG_OUTPUT_POWER_SETPOINT = 0x21
    REG_CURRENT_SETPOINT = 0x27
    REG_EMISSION = 0x30
    REG_SETUP_BITS = 0x31
    REG_INTERLOCK = 0x32
    REG_WATCHDOG_TIMER = 0x36
    REG_NIM_DELAY = 0x3B
    REG_MODEL_SERIAL_NUMBER = 0x65

    REG_STATUS_BITS = 0x66

    REG_USER_AREA = 0x8D

    REG_IP_ADDRESS = 0xB0
    REG_GATEWAY = 0xB1
    REG_SUBNET_MASK = 0xB2
    REG_MAC_ADDRESS = 0xB3


class Varia(Enum):
    DEVICE_ID = 16

    # SuperK VARIA registers
    REG_MONITOR_INPUT = 0x13

    REG_ND_SETPOINT = 0x32
    REG_SWP_SETPOINT = 0x33
    REG_LWP_SETPOINT = 0x34

    REG_STATUS_BITS = 0x66


def read_register(read_func, register, *, ratio=1, index=-1):
    def getter(self):
        device_id = register.__class__.DEVICE_ID

        future = self.pool.submit(read_func, self.port, device_id.value, register.value, index)
        result, value = future.result()

        self.check_result(result)

        return value * ratio

    return getter

def write_register(write_func, register, *, ratio=1, index=-1):
    def setter(self, value):
        device_id = register.__class__.DEVICE_ID

        # Convert the value to the register value. This assumes integer types.
        register_value = int(value / ratio)

        self.log.debug(f'Writing value {register_value} to {register}.')

        future = self.pool.submit(write_func, self.port, device_id.value, register.value, register_value, index)
        result = future.result()

        self.check_result(result)

    return setter

class NktSuperk(Service):
    '''The service for both the NKT SuperK EVO and NKT SuperK VARIA.

    Both devices are combined into a single service due to the need for
    a single open port to the device that cannot be shared between
    multiple services.
    '''
    def __init__(self):
        super().__init__('nkt_superk')

        self.threads = {}
        self.port = self.config['port']

    def open(self):
        # Make datastreams.
        self.base_temperature = self.make_data_stream('base_temperature', 'float32', [1], 20)
        self.supply_voltage = self.make_data_stream('supply_voltage', 'float32', [1], 20)
        self.external_control_input = self.make_data_stream('external_control_input', 'float32', [1], 20)

        self.emission = self.make_data_stream('emission', 'uint8', [1], 20)
        self.power_setpoint = self.make_data_stream('power_setpoint', 'float32', [1], 20)
        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)

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
        self.current_setpoint.submit_data(np.array([self.config['current_setpoint']], dtype='float32'))

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
            'current_setpoint': self.monitor_func(self.current_setpoint, self.set_current_setpoint),
            'varia_status': self.update_func(self.update_varia_status),
            'evo_status': self.update_func(self.update_evo_status)
        }

        # Create a pool with a single worker to perform communication with the device.
        self.pool = ThreadPoolExecutor(max_workers=1)

        # Open port.
        # Make sure that the device is available (ie. not being used by someone else).
        # This is not strictly necessary according to the SDK, but speeds up reading/writing.
        future = self.pool.submit(openPorts, self.port, autoMode=0, liveMode=0)
        self.check_result(future.result())

        # Start all threads.
        for key, func in funcs.items():
            thread = threading.Thread(target=func)
            thread.start()

            self.threads[key] = thread

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        # Join all threads.
        for thread in self.threads.values():
            thread.join()

        # Close port.
        future = self.pool.submit(closePorts, self.port)
        self.check_result(future.result())

        # Close pool.
        self.pool.shutdown()

    def check_result(self, result):
        if result != 0:
            self.log.error('NKT error: ' + RegisterResultTypes(result))
            raise RuntimeError(RegisterResultTypes(result))

    def update_evo_status(self):
        temperature = self.get_base_temperature()
        self.base_temperature.submit_data(np.array([temperature], dtype='float32'))

        voltage = self.get_supply_voltage()
        self.supply_voltage.submit_data(np.array([voltage], dtype='float32'))

        control_input = self.get_external_control_input()
        self.external_control_input.submit_data(np.array([control_input], dtype='float32'))

    def update_varia_status(self):
        status = self.get_varia_status_bits()

        # Extract moving filters from status.
        nd_filter_moving = (status & (2 << 12)) > 0
        swp_filter_moving = (status & (2 << 13)) > 0
        lwp_filter_moving = (status & (2 << 14)) > 0

        # Submit results to their respective datastreams.
        self.nd_filter_moving.submit_data(np.array([nd_filter_moving], dtype='uint8'))
        self.swp_filter_moving.submit_data(np.array([swp_filter_moving], dtype='uint8'))
        self.lwp_filter_moving.submit_data(np.array([lwp_filter_moving], dtype='uint8'))

        # Update input monitor.
        monitor_input = self.get_monitor_input()
        self.monitor_input.submit_data(np.array([monitor_input], dtype='float32'))

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

    # Functions for the SuperK EVO
    get_base_temperature = read_register(registerReadS16, Evo.REG_BASE_TEMPERATURE, ratio=0.1)
    get_supply_voltage = read_register(registerReadU16, Evo.REG_SUPPLY_VOLTAGE, ratio=0.001)
    get_external_control_input = read_register(registerReadU16, Evo.REG_EXTERNAL_CONTROL_INPUT, ratio=0.001)

    get_power_setpoint = read_register(registerReadU16, Evo.REG_OUTPUT_POWER_SETPOINT, ratio=0.1)
    set_power_setpoint = write_register(registerWriteU16, Evo.REG_OUTPUT_POWER_SETPOINT, ratio=0.1)

    get_current_setpoint = read_register(registerReadU16, Evo.REG_CURRENT_SETPOINT, ratio=0.1)
    set_current_setpoint = write_register(registerWriteU16, Evo.REG_CURRENT_SETPOINT, ratio=0.1)

    get_emission = read_register(registerReadU8, Evo.REG_EMISSION, ratio=0.5)
    set_emission = write_register(registerWriteU8, Evo.REG_EMISSION, ratio=0.5)

    get_setup_bits = read_register(registerReadU8, Evo.REG_SETUP_BITS)
    set_setup_bits = write_register(registerWriteU8, Evo.REG_SETUP_BITS)

    get_interlock_msb = read_register(registerReadU8, Evo.REG_INTERLOCK, index=0)
    get_interlock_lsb = read_register(registerReadU8, Evo.REG_INTERLOCK, index=1)

    get_evo_status_bits = read_register(registerReadU16, Evo.REG_STATUS_BITS)

    get_watchdog_timer = read_register(registerReadU8, Evo.REG_WATCHDOG_TIMER)
    set_watchdog_timer = write_register(registerWriteU8, Evo.REG_WATCHDOG_TIMER)

    # Functions for the SuperK VARIA
    get_monitor_input = read_register(registerReadU16, Varia.REG_MONITOR_INPUT, ratio=0.1)

    get_nd_setpoint = read_register(registerReadU16, Varia.REG_ND_SETPOINT, ratio=0.1)
    get_swp_setpoint = read_register(registerReadU16, Varia.REG_SWP_SETPOINT, ratio=0.1)
    get_lwp_setpoint = read_register(registerReadU16, Varia.REG_LWP_SETPOINT, ratio=0.1)

    set_nd_setpoint = write_register(registerWriteU16, Varia.REG_ND_SETPOINT, ratio=0.1)
    set_swp_setpoint = write_register(registerWriteU16, Varia.REG_SWP_SETPOINT, ratio=0.1)
    set_lwp_setpoint = write_register(registerWriteU16, Varia.REG_LWP_SETPOINT, ratio=0.1)

    get_varia_status_bits = read_register(registerReadU16, Varia.REG_STATUS_BITS)


if __name__ == '__main__':
    service = NktSuperk()
    service.run()
