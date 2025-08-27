from catkit2.base_services.nkt_superk import NktSuperk, read_register, write_register

import numpy as np
from enum import Enum

try:
    from NKTP_DLL import *
except ImportError:
    print('To use NKT SDK, you need to install the SDK and check the NKTP_SDK_PATH environment variable.')
    raise


class Fianium(Enum):
    """Registers for the NKT SuperK FIANIUM device."""
    DEVICE_ID = 15
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


class NktSuperkFianium(NktSuperk):
    '''The service for both the NKT SuperK FIANIUM and NKT SuperK VARIA.

    Both devices are combined into a single service due to the need for
    a single open port to the device that cannot be shared between
    multiple services.
    '''
    def __init__(self):
        super().__init__('nkt_superk_fianium')
        self.pulse_picker_safety = self.config.get('pulse_picker_safety')

    def _create_device_specific_streams(self):
        """Create FIANIUM-specific data streams."""
        # FIANIUM-specific streams
        self.power_setpoint = self.make_data_stream('power_setpoint', 'float32', [1], 20)
        self.pulse_picker_ratio = self.make_data_stream('pulse_picker_ratio', 'uint16', [1], 20)

        # Set initial FIANIUM setpoints from config
        self.power_setpoint.submit_data(np.array([self.config['power_setpoint']], dtype='float32'))
        self.pulse_picker_ratio.submit_data(np.array([100], dtype='uint16'))  # Setting a safe default value of 100.

    def _get_device_specific_funcs(self):
        """Get FIANIUM-specific thread functions."""
        return {
            'power_setpoint': self.monitor_func(self.power_setpoint, self.set_power_setpoint),
            'pulse_picker_ratio': self.monitor_pulse_picker_ratio(self.pulse_picker_ratio, self.set_pulse_picker_ratio)
        }

    def _device_specific_cleanup(self):
        """Perform FIANIUM-specific cleanup."""
        # Set pulse picker ratio to safe value
        self.pulse_picker_ratio.submit_data(np.array([100], dtype='uint16'))

    def monitor_pulse_picker_ratio(self, stream, setter):
        """Monitor pulse picker ratio with safety checks."""
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


if __name__ == '__main__':
    service = NktSuperkFianium()
    service.run()
