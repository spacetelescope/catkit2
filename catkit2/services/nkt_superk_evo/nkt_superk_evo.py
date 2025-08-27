from catkit2.base_services.nkt_superk_base import NktSuperkBase, read_register, write_register

import numpy as np
from enum import Enum

try:
    from NKTP_DLL import *
except ImportError:
    print('To use NKT SDK, you need to install the SDK and check the NKTP_SDK_PATH environment variable.')
    raise


class Evo(Enum):
    """Registers for the NKT SuperK EVO device."""
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


class NktSuperkEvo(NktSuperkBase):
    '''The service for both the NKT SuperK EVO and NKT SuperK VARIA.

    Both devices are combined into a single service due to the need for
    a single open port to the device that cannot be shared between
    multiple services.
    '''
    def __init__(self):
        super().__init__('nkt_superk_evo')

    def _create_device_specific_streams(self):
        """Create EVO-specific data streams."""
        # EVO-specific streams
        self.base_temperature = self.make_data_stream('base_temperature', 'float32', [1], 20)
        self.supply_voltage = self.make_data_stream('supply_voltage', 'float32', [1], 20)
        self.external_control_input = self.make_data_stream('external_control_input', 'float32', [1], 20)

        self.power_setpoint = self.make_data_stream('power_setpoint', 'float32', [1], 20)
        self.current_setpoint = self.make_data_stream('current_setpoint', 'float32', [1], 20)

        # Set initial EVO setpoints from config
        self.power_setpoint.submit_data(np.array([self.config['power_setpoint']], dtype='float32'))
        self.current_setpoint.submit_data(np.array([self.config['current_setpoint']], dtype='float32'))

    def _get_device_specific_funcs(self):
        """Get EVO-specific thread functions."""
        return {
            'power_setpoint': self.monitor_func(self.power_setpoint, self.set_power_setpoint),
            'current_setpoint': self.monitor_func(self.current_setpoint, self.set_current_setpoint),
            'evo_status': self.update_func(self.update_evo_status)
        }

    def _device_specific_cleanup(self):
        """Perform EVO-specific cleanup."""
        # No specific cleanup needed for EVO
        pass

    def update_evo_status(self):
        """Update EVO-specific status information."""
        temperature = self.get_base_temperature()
        self.base_temperature.submit_data(np.array([temperature], dtype='float32'))

        voltage = self.get_supply_voltage()
        self.supply_voltage.submit_data(np.array([voltage], dtype='float32'))

        control_input = self.get_external_control_input()
        self.external_control_input.submit_data(np.array([control_input], dtype='float32'))

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


if __name__ == '__main__':
    service = NktSuperkEvo()
    service.run()
