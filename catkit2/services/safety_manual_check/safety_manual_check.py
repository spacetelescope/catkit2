from catkit2.testbed import Service

import numpy as np

class SafetyManualCheck(Service):
    def __init__(self):
        super().__init__('safety_manual_check')

        self.dtype = self.config['dtype']
        self.value = np.array([self.config['initial_value']], dtype=self.dtype)

        self.make_property('value', self.get_value, self.set_value)

        self.check_stream = self.make_data_stream('check', item_type, [1], 20)

    def main(self):
        while not self.should_shut_down:
            self.check_stream.submit_data(self.value)

            self.sleep(0.1)

    def get_value(self):
        return self.check_value[0]

    def set_value(self, new_value):
        # This makes sure that the new value is actually convertable to a self.dtype.
        self.value = np.array([new_value], dtype=self.dtype)

if __name__ == '__main__':
    service = SafetyManualCheck()
    service.run()
