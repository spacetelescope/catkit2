import time
from catkit2.testbed.service import Service


class ThorlabsFW102CDllSim(Service):
    def __init__(self):
        super().__init__('thorlabs_fw102c_dll_sim')

        self.serial = self.config['serial']
        self.hdl = None
        self._position = 1

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
        self.log.info("Connect %s successful", self.serial)

    def main(self):
        while not self.should_shut_down:
            time.sleep(0.1)

    def close(self):
        self.log.info("Close %s successful", self._position)

    def get_position(self):
        # self.log.info("Get Position: %d", pos[0])
        return self._position

    def set_position(self, position: int):
        self._position = position
        self.log.info("Position is %d", position)

    @property
    def position(self):
        return self.get_position()

    @position.setter
    def position(self, position: int):
        return self.set_position(position)


if __name__ == '__main__':
    service = ThorlabsFW102CDllSim()
    service.run()
