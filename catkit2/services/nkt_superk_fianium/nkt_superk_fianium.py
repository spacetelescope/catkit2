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


class Fianium(Enum):
    """Registers for the NKT SuperK FIANIUM device."""
    # Bus address is discovered at runtime by module type (see MODULE_TYPE);
    # this value is only a fallback default if discovery is disabled.
    DEVICE_ID = 15
    # Module type reported by register 0x61 (SuperK FIANIUM main board).
    MODULE_TYPE = 0x88
    REG_EMISSION = 0x30
    REG_SETUP_BITS = 0x31
    REG_INTERLOCK = 0x32
    REG_PULSE_PICKER_RATIO = 0x34
    REG_WATCHDOG_TIMER = 0x36
    REG_OUTPUT_LEVEL = 0x37
    REG_NIM_DELAY = 0x39
    REG_MODULE_TYPE = 0x61
    REG_MODEL_SERIAL_NUMBER = 0x65
    REG_STATUS_BITS = 0x66
    REG_ERROR_CODE = 0x67


class Varia(Enum):
    # Bus address is discovered at runtime by module type (see MODULE_TYPE);
    # this value is only a fallback default if discovery is disabled. The VARIA
    # enumerates by daisy-chain position, so its address is not fixed.
    DEVICE_ID = 16
    # Module type reported by register 0x61 (SuperK VARIA, A301).
    MODULE_TYPE = 0x68

    # SuperK VARIA registers
    REG_MONITOR_INPUT = 0x13

    REG_ND_SETPOINT = 0x32
    REG_SWP_SETPOINT = 0x33
    REG_LWP_SETPOINT = 0x34

    REG_STATUS_BITS = 0x66


def read_register(read_func, register, *, ratio=1, index=-1):
    def getter(self):
        device_id = self.device_address(register.__class__)

        future = self.pool.submit(read_func, self.port, device_id, register.value, index)
        result, value = future.result()

        self.check_result(result)

        return value * ratio

    return getter


def write_register(write_func, register, *, ratio=1, index=-1):
    def setter(self, value):
        device_id = self.device_address(register.__class__)

        # Convert the value to the register value. This assumes integer types.
        register_value = int(value / ratio)

        self.log.debug(f'Writing value {register_value} to {register}.')

        future = self.pool.submit(write_func, self.port, device_id, register.value, register_value, index)
        result = future.result()

        self.check_result(result)

    return setter


class NktSuperkFianium(Service):
    '''The service for both the NKT SuperK FIANIUM and NKT SuperK VARIA.

    Both devices are combined into a single service due to the need for
    a single open port to the device that cannot be shared between
    multiple services.
    '''
    def __init__(self):
        super().__init__('nkt_superk_fianium')

        self.threads = {}
        self.port = self.config['port']

        # Bus addresses are discovered at runtime by module type (see
        # discover_devices), because NKT modules enumerate by daisy-chain
        # position and are not at fixed addresses. Falls back to each enum's
        # DEVICE_ID until discovery runs.
        self.device_addresses = {device: device.DEVICE_ID.value for device in (Fianium, Varia)}

        # This is a safety-critical guard against burning the VARIA fibers on
        # bandwidth increases, so a missing value must fail loudly here rather
        # than silently become None and crash a monitor thread later on.
        self.pulse_picker_safety = self.config.get('pulse_picker_safety')
        if self.pulse_picker_safety is None:
            raise KeyError("Missing required config key 'pulse_picker_safety' for the nkt_superk service.")

        # In live mode the kernel enumerates the bus in the background, so give
        # the address sweep a few retries before treating a module as absent.
        self.device_scan_retries = self.config.get('device_scan_retries', 10)
        self.device_scan_retry_interval = self.config.get('device_scan_retry_interval', 0.2)
        # Highest bus address to probe when discovering module addresses.
        self.device_scan_max_address = self.config.get('device_scan_max_address', 25)

    def open(self):
        # Make datastreams.
        self.emission = self.make_data_stream('emission', 'uint8', [1], 20)
        self.power_setpoint = self.make_data_stream('power_setpoint', 'float32', [1], 20)
        self.pulse_picker_ratio = self.make_data_stream('pulse_picker_ratio', 'uint16', [1], 20)

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

        # Start at the brightest fiber-safe pulse-picker ratio for the configured
        # bandwidth: max(int(bandwidth / pulse_picker_safety), 1). A higher ratio
        # passes fewer pulses (less power); going below this risks burning the
        # VARIA fibers, so this is the safety floor, not an arbitrary default.
        startup_bandwidth = self.config['swp_setpoint'] - self.config['lwp_setpoint']
        safe_pulse_picker_ratio = max(int(startup_bandwidth / self.pulse_picker_safety), 1)
        self.pulse_picker_ratio.submit_data(np.array([safe_pulse_picker_ratio], dtype='uint16'))

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
            'pulse_picker_ratio': self.monitor_pulse_picker_ratio(self.pulse_picker_ratio, self.set_pulse_picker_ratio),
            'varia_status': self.update_func(self.update_varia_status)
        }

        # Create a pool with a single worker to perform communication with the device.
        self.pool = ThreadPoolExecutor(max_workers=1)

        # Open port.
        # liveMode=1 makes the kernel actively scan and register every module on
        # the bus. Without it (liveMode=0) the FIANIUM main board (device 15) still
        # answers, but the VARIA (device 16) is never enumerated and NACKs every
        # read/write. autoMode=0 keeps us pinned to the explicitly configured port.
        future = self.pool.submit(openPorts, self.port, autoMode=0, liveMode=1)
        self.check_result(future.result())

        # Discover the bus address of each module by its module type. This must
        # run before any monitor thread starts reading/writing setpoints.
        self.discover_devices()

        # Start all threads.
        for key, func in funcs.items():
            thread = threading.Thread(target=func)
            thread.start()

            self.threads[key] = thread

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        self.pulse_picker_ratio.submit_data(np.array([100], dtype='uint16'))

        # Turn off the source
        self.set_emission(0)

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

    def device_address(self, device):
        '''Return the discovered bus address for a device enum (Fianium or Varia).'''
        return self.device_addresses[device]

    def discover_devices(self):
        '''Find the bus address of each module by reading its module-type register.

        NKT modules enumerate by daisy-chain position, so their bus addresses
        are not fixed (e.g. the VARIA may sit at 16, 20, ...). We sweep the bus,
        read the module-type register (0x61) at each address, and match against
        the MODULE_TYPE each device enum declares. Every module we depend on
        must be found or we fail here with a clear message, rather than letting
        the monitor threads die one by one on NACKs.

        With live mode the kernel scans the bus in the background, so a module
        may not answer on the very first sweep right after openPorts. We retry
        the whole sweep briefly to absorb that latency.
        '''
        wanted = {device.MODULE_TYPE.value: device for device in (Fianium, Varia)}
        module_type_register = 0x61

        found = {}
        for _ in range(self.device_scan_retries):
            for address in range(self.device_scan_max_address + 1):
                future = self.pool.submit(registerReadU8, self.port, address, module_type_register, -1)
                result, module_type = future.result()

                if result == 0 and module_type in wanted:
                    device = wanted[module_type]
                    found[device] = address

            if all(device in found for device in wanted.values()):
                break

            self.sleep(self.device_scan_retry_interval)

        missing = [device for device in wanted.values() if device not in found]
        if missing:
            names = ', '.join(f'{d.__name__} (type 0x{d.MODULE_TYPE.value:02x})' for d in missing)
            raise RuntimeError(
                f'Could not find NKT module(s) {names} on port {self.port}. Check that the '
                f'module is powered on and connected to the bus.')

        self.device_addresses.update(found)
        for device, address in found.items():
            self.log.info(f'Found NKT {device.__name__} at bus address {address}.')

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

    def monitor_pulse_picker_ratio(self, stream, setter):
        def func():
            while not self.should_shut_down:
                try:
                    frame = stream.get_next_frame(1)
                except Exception:
                    continue

                bandwidth = self.swp_setpoint.get()[0] - self.lwp_setpoint.get()[0]
                if frame.data[0] >= max(int(bandwidth / self.pulse_picker_safety), 1):
                    setter(frame.data[0])
                else:
                    self.log.warning(f'Pulse picker ratio {frame.data[0]} is too low for the current bandwidth {bandwidth}. Not setting it.')

        return func

    def update_func(self, updater):
        def func():
            while not self.should_shut_down:
                updater()

                self.sleep(1)

        return func

    # Functions for the SuperK FIANIUM
    get_power_setpoint = read_register(registerReadU16, Fianium.REG_OUTPUT_LEVEL, ratio=0.1)
    set_power_setpoint = write_register(registerWriteU16, Fianium.REG_OUTPUT_LEVEL, ratio=0.1)

    get_emission = read_register(registerReadU8, Fianium.REG_EMISSION, ratio=1)
    set_emission = write_register(registerWriteU8, Fianium.REG_EMISSION, ratio=1)

    get_setup_bits = read_register(registerReadU8, Fianium.REG_SETUP_BITS)
    set_setup_bits = write_register(registerWriteU8, Fianium.REG_SETUP_BITS)

    get_interlock_msb = read_register(registerReadU8, Fianium.REG_INTERLOCK, index=0)
    get_interlock_lsb = read_register(registerReadU8, Fianium.REG_INTERLOCK, index=1)

    get_fianium_status_bits = read_register(registerReadU16, Fianium.REG_STATUS_BITS)

    get_watchdog_timer = read_register(registerReadU8, Fianium.REG_WATCHDOG_TIMER)
    set_watchdog_timer = write_register(registerWriteU8, Fianium.REG_WATCHDOG_TIMER)

    get_pulse_picker_ratio = read_register(registerReadU16, Fianium.REG_PULSE_PICKER_RATIO, ratio=1)
    set_pulse_picker_ratio = write_register(registerWriteU16, Fianium.REG_PULSE_PICKER_RATIO, ratio=1)

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
    service = NktSuperkFianium()
    service.run()
