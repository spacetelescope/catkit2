import time
from catkit2.testbed.service import Service

try:
    from FWxC_COMMAND_LIB import (
        FWxCOpen,
        FWxCClose,
        FWxCGetPosition,
        FWxCSetPosition,
        FWxCListDevices,
        FWxCSetTriggerMode,
        FWxCSetSpeedMode,
        FWxCSetSensorMode
    )
except OSError as ex:
    print("Warning:", ex)


class ThorlabsFW102CDll(Service):
    def __init__(self):
        super().__init__('thorlabs_fw102c_dll')

        self.serial = self.config['serial']
        devs = FWxCListDevices()
        if len(devs) <= 0:
            raise RuntimeError("There is no devices connected")
        if self.serial not in [dev[0] for dev in devs]:
            raise RuntimeError("Device %s not found", self.serial)
        self.hdl = None

        def make_property_helper(property_name, read_only=False, dtype=None):
            if dtype is None:
                dtype = ''

            def getter():
                return getattr(self, property_name)

            if read_only:
                self.make_property(property_name, getter, type=dtype)
                return

            def setter(value):
                setattr(self, property_name, value)

            self.make_property(property_name, getter, setter, type=dtype)

        make_property_helper('position', dtype='int64')

        # self.make_command('get_position', self.get_position)
        # self.make_command('set_position', self.set_position)

    def open(self):
        self.hdl = FWxCOpen(self.serial, 115200, 3)
        if self.hdl < 0:
            raise RuntimeError(f"Connect {self.serial} fail")

        # 0: input mode, 1: output mode
        result = FWxCSetTriggerMode(self.hdl, 0)
        if result < 0:
            self.log.warning("Set Trigger Mode fail")

        # 0: slow speed, 1: high speed
        result = FWxCSetSpeedMode(self.hdl, 1)
        if result < 0:
            self.log.warning("Set Speed Mode fail")

        # 0: Sensors turn off, 1: Sensors remain active
        result = FWxCSetSensorMode(self.hdl, 0)
        if result < 0:
            self.log.warning("Set Sensor Mode fail")

        self.log.info("Connect %s successful", self.serial)

    def main(self):
        while not self.should_shut_down:
            time.sleep(0.1)

    def close(self):
        if self.hdl is None:
            raise RuntimeError("Device not connected")
        FWxCClose(self.hdl)
        self.log.info("Close %s successful", self.serial)

    def get_position(self):
        if self.hdl is None:
            return -1
        pos = [-1]

        result = FWxCGetPosition(self.hdl, pos)
        if result < 0 and pos[0] < 0:
            self.log.error("Get Position fail")
            return -1

        # self.log.info("Get Position: %d", pos[0])
        return pos[0]

    def set_position(self, position: int):
        if self.hdl is None:
            raise RuntimeError("Device not connected")
        result = FWxCSetPosition(self.hdl, position)
        if result < 0:
            self.log.error("Set Position fail")
            return -1

        self.log.info("Position is %d", position)

    @property
    def position(self):
        return self.get_position()

    @position.setter
    def position(self, position: int):
        return self.set_position(position)


if __name__ == '__main__':
    service = ThorlabsFW102CDll()
    service.run()
