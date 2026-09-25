from catkit2.base_services.nkt_superk import read_register, write_register
from catkit2.base_services.nkt_superk_fianium import NktSuperkFianium

from enum import Enum

try:
    from NKTP_DLL import *
except ImportError:
    raise RuntimeError('NKT SDK is required for hardware services but not available. '
                       'Install the SDK and check the NKTP_SDK_PATH environment variable.')


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


class NktSuperkFianiumHardware(NktSuperkFianium):
    '''The hardware service for both the NKT SuperK FIANIUM and NKT SuperK VARIA.

    Both devices are combined into a single service due to the need for
    a single open port to the device that cannot be shared between
    multiple services.
    '''
    def __init__(self):
        super().__init__('nkt_superk_fianium_hardware')

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
    service = NktSuperkFianiumHardware()
    service.run()
