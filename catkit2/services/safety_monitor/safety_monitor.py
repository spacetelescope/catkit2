from catkit2.protocol.service import Service, parse_service_args
from catkit2.protocol.client import TestbedClient
from catkit2.catkit_bindings import get_timestamp

import time
import sys
import numpy as np

class SafetyMonitor(Service):
    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'safety_monitor', testbed_port)

        self.testbed = TestbedClient(testbed_port)

        config = self.configuration
        self.check_interval = config['check_interval']
        self.safeties = config['safeties']
        self.checked_safeties = list(sorted(self.safeties.keys()))

        self.shutdown_flag = False

        self.data_streams = {}

        self.is_safe = self.make_data_stream('is_safe', 'int8', [len(self.safeties)], 20)

        self.make_property('checked_safeties', lambda: self.checked_safeties)

    def check_safety(self):
        current_time = get_timestamp()

        is_safes = np.zeros(len(self.safeties), dtype='int8')

        for i, safety_name in enumerate(self.checked_safeties):
            safety_info = self.safeties[safety_name]

            try:
                last_frame = self.data_streams[safety_name].get_latest_frame()
            except:
                last_frame = self.data_streams[safety_name].get_next_frame()

            is_safe = True

            # Check if frame is too old.
            timestamp_lower_bound = current_time - safety_info['safe_interval'] * 1e9
            if last_frame.timestamp < timestamp_lower_bound:
                is_safe = False

            # Check value lower bound.
            if last_frame.data[0] < safety_info['minimum_value']:
                is_safe = False

            # Check value upper bound.
            if last_frame.data[0] > safety_info['maximum_value']:
                is_safe = False

            # Report if conditions are safe.
            is_safes[i] = is_safe

        # Submit safety.
        self.is_safe.submit_data(is_safes)

    def open(self):
        for safety_name in self.checked_safeties:
            safety = self.safeties[safety_name]

            service = getattr(self.testbed, safety['service_name'])
            self.data_streams[safety_name] = getattr(service, safety['stream_name'])

    def main(self):
        while not self.shutdown_flag:
            start = time.time()

            self.check_safety()

            while not self.shutdown_flag and time.time() < (start + self.check_interval):
                time.sleep(0.05)

    def close(self):
        self.data_streams = {}

    def shut_down(self):
        self.shutdown_flag = True

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = SafetyMonitor(service_name, testbed_port)
    service.run()
