import ctypes
import sys
import glob
import os

from hicat2.protocol.service import Service, parse_service_args

class ThorlabsTSP01Sim(Serivce):
    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'thorlabs_tsp01_sim', testbed_port)

        self.shutdown_flag = False

        self.temperature_internal = self.make_data_stream('temperature_internal', 'float64', [1], 20)
        self.temperature_header_1 = self.make_data_stream('temperature_header_1', 'float64', [1], 20)
        self.temperature_header_2 = self.make_data_stream('temperature_header_2', 'float64', [1], 20)
        self.humidity_internal = self.make_data_stream('humidity_internal', 'float64', [1], 20)

    def main(self):
        while not self.shutdown_flag:
            t1 = self.get_temperature(1)
            t2 = self.get_temperature(2)
            t3 = self.get_temperature(3)
            h = self.get_humidity()

            self.temperature_internal.submit_data(np.array([t1]))
            self.temperature_header_1.submit_data(np.array([t2]))
            self.temperature_header_2.submit_data(np.array([t3]))
            self.humidity_internal.submit_data(np.array([h]))

            time.sleep(1)

    def shutdown(self):
        self.shutdown_flag = True

    def get_temperature(self, channel):
        return 25

    def get_humidity(self):
        return 20

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = ThorlabsTSP01Sim(service_name, testbed_port)
    service.run()
