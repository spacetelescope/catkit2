from catkit2.testbed.service import Service

import functools

from NKTP_DLL import *

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

# TODO: check thread safety of NKT API.
def read_register(read_func, register, *, ratio=1, index=-1):
    def getter(self):
        result, value = read_func(self.port, DEVICE_ID, register, index)

        self.check_result(result)

        return value * ratio

    return getter

# TODO: check thread safety of NKT API.
def write_register(write_func, register, *, ratio=1, index=-1):
    def setter(self, value):
        # Convert the value to the register value. This assumes integer types.
        register_value = int(value / ratio)
        result = write_func(self.port, DEVICE_ID, register, register_value, index)

        self.check_result(result)

    return setter

class NktSuperkEvo(Service):
    def __init__(self):
        super().__init__('nkt_superk_evo')

    def open(self):
        # Open port.
        # Make sure that the device is available (ie. not being used by someone else).
        # This is not strictly necessary according to the SDK, but speeds up reading/writing.
        # However, I think it's necessary if we want to use the watchdog timer (for safety).

        self.base_temperature = self.make_data_stream('base_temperature', 'float32', [1], 20)
        self.supply_voltage = self.make_data_stream('supply_voltage', 'float32', [1], 20)
        self.get_external_control_input = self.make_data_stream('external_control_input', 'float32', [1], 20)

        self.make_property('power_setpoint', self.get_power_setpoint, self.set_power_setpoint)
        self.make_property('current_setpoint', self.get_current_setpoint, self.set_current_setpoint)
        self.make_property('emission', self.get_emission, self.set_emission)

    def main(self):
        while not self.should_shut_down:
            temperature = self.get_base_temperature()
            self.base_temperature.submit_data(np.array([temperature], dtype='float32'))

            voltage = self.get_supply_voltage()
            self.supply_voltage.submit_data(np.array([voltage], dtype='float32'))

            control_input = self.get_external_control_input()
            self.get_external_control_input.submit_data(np.array([control_input], dtype='float32'))

            self.sleep(1)

    def close(self):
        # Close port.
        pass

    def check_result(self, result):
        if result != 0:
            self.log.error('Register error: ' + RegisterResultTypes(result))
            raise RuntimeError(RegisterResultTypes(result))

    get_base_temperature = read_register(registerReadS16, REG_BASE_TEMPERATURE, ratio=0.1)
    get_supply_voltage = read_register(registerReadU16, REG_SUPPLY_VOLTAGE, ratio=0.001)
    get_external_control_input = read_register(registerReadU16, REG_EXTERNAL_CONTROL_INPUT, ratio=0.001)

    get_power_setpoint = read_register(registerReadU16, REG_OUTPUT_POWER_SETPOINT, ratio=0.1)
    set_power_setpoint = write_register(registerWriteU16, REG_OUTPUT_POWER_SETPOINT, ratio=0.1)

    get_current_setpoint = read_register(registerReadU16, REG_CURRENT_SETPOINT, ratio=0.1)
    set_current_setpoint = write_register(registerWriteU16, REG_CURRENT_SETPOINT, ratio=0.1)

    get_emission = read_register(registerReadU8, REG_EMISSION, ratio=0.5)
    set_emission = write_register(registerWriteU8, REG_EMISSION, ratio=0.5)

    get_setup_bits = read_register(registerReadU8, REG_SETUP_BITS)
    set_setup_bits = write_register(registerWriteU8, REG_SETUP_BITS)

    get_interlock_msb = read_register(registerReadU8, REG_INTERLOCK, index=0)
    get_interlock_lsb = read_register(registerReadU8, REG_INTERLOCK, index=1)

    get_status_bits = read_register(registerReadS16, REG_STATUS_BITS)

    get_watchdog_timer = read_register(registerReadU8, REG_WATCHDOG_TIMER)
    set_watchdog_timer = write_register(registerWriteU8, REG_WATCHDOG_TIMER)

if __name__ == '__main__':
    service = NktSuperkEvo()
    service.run()
