from catkit2.testbed.service import Service

import numpy as np

class SnmpUpsSim(Service):
    def __init__(self):
        super().__init__('snmp_ups_sim')

        self.check_interval = self.config.get('check_interval', 30)

        self.power_ok = self.make_data_stream('power_ok', 'int8', [1], 20)

    def get_power_ok(self):
        return True

    def open(self):
        # Do one check on power safety during opening.
        # This is to make sure that we always have at least one power check in the datastream.
        power_ok = self.get_power_ok()
        self.power_ok.submit_data(np.array([power_ok], dtype='int8'))

    def main(self):
        while not self.should_shut_down:
            power_ok = self.get_power_ok()
            self.power_ok.submit_data(np.array([power_ok], dtype='int8'))

            self.sleep(self.check_interval)

if __name__ == '__main__':
    service = SnmpUpsSim()
    service.run()
