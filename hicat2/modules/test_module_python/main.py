from hicat2.bindings import Module, DataStream
from hicat2.testbed import parse_module_args
import time
import numpy as np

class TestModule(Module):
    def __init__(self):
        args = parse_module_args()
        Module.__init__(self, args.module_name, args.module_port)

        self.shutdown_flag = False

        self.temperature = DataStream.create('temperature', self.name, 'float64', [1], 20)
        self.humidity = DataStream.create('humidity', self.name, 'float64', [1], 20)

        self.register_data_stream(self.temperature)
        self.register_data_stream(self.humidity)

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
        print('Got shutdown')
        self.shutdown_flag = True

    def open(self):
        pass

    def get_temperature(self, channel):
        return np.sin(time.time())

    def get_humidity(self):
        return np.cos(time.time())

    def close(self):
        return 0

def main():
    module = TestModule()
    module.run()

if __name__ == '__main__':
    main()
