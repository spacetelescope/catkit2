from hicat2.bindings import Module, DataStream
import time

class TestModule(Module):
    def __init__(self):
        Module.__init__(self, 'test_module', 8080)

        self.shutdown_flag = False

        self.temperature = DataStream.create(self.name + '_temperature', 'float64', [2], 20)
        self.humidity = DataStream.create(self.name + '_humidity', 'float64', [2], 20)

        self.register_data_stream(self.temperature)
        self.register_data_stream(self.humidity)

    def main(self):
        self.open()

        print('measured2')

        while not self.shutdown_flag:
            f = self.temperature.request_new_frame()
            f.data[:] = self.get_temperature(1)
            self.temperature.submit_frame(f.id)

            f = self.humidity.request_new_frame()
            f.data[:] = self.get_humidity()
            self.humidity.submit_frame(f.id)

            print('measured')
            time.sleep(1)

        self.close()

    def shut_down(self):
        print('Got shutdown')
        self.shutdown_flag = True

    def open(self):
        pass

    def get_temperature(self, channel):
        return 0

    def get_humidity(self):
        return 0

    def close(self):
        return 0

def main():
    module = TestModule()
    module.main()

if __name__ == '__main__':
    main()
