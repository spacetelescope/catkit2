from hicat2.bindings import Module, DataStream, Command, Property
from hicat2.testbed import parse_module_args
import time
import numpy as np

class TestModule(Module):
    def __init__(self):
        args = parse_module_args()
        Module.__init__(self, args.module_name, args.module_port)

        self.shutdown_flag = False

        self.temperature = DataStream.create('temperature', self.name, 'float64', [1], 20)
        self.register_data_stream(self.temperature)

        self.humidity = DataStream.create('humidity', self.name, 'float64', [1], 20)
        self.register_data_stream(self.humidity)

        self.test_command = Command('test', self.test)
        self.register_command(self.test_command)

        self.test_property = Property('test_prop', self.test_getter, self.test_setter)
        self.register_property(self.test_property)
        self._test = 46346345

    def test(self, args):
        print('did something with', args)
        return 356

    def test_getter(self):
        return self._test

    def test_setter(self, val):
        self._test = val

    def main(self):
        self.open()

        while not self.shutdown_flag:
            f = self.temperature.request_new_frame()
            f.data[:] = self.get_temperature(1)
            self.temperature.submit_frame(f.id)

            f = self.humidity.request_new_frame()
            f.data[:] = self.get_humidity()
            self.humidity.submit_frame(f.id)

            time.sleep(0.5)

        self.close()

    def shut_down(self):
        self.shutdown_flag = True

    def open(self):
        pass

    def get_temperature(self, channel):
        return 20 + 3 * np.sin(0.1 * time.time())

    def get_humidity(self):
        return 10 + 2 * np.cos(0.1 * time.time())

    def close(self):
        return 0

def main():
    module = TestModule()
    module.run()

if __name__ == '__main__':
    main()
