from catkit2.testbed import Service
from catkit2.catkit_bindings import get_timestamp

import time
import sys
import numpy as np

class SafetyMonitor(Service):
    def __init__(self):
        super().__init__('safety_monitor')

        self.check_interval = self.config['check_interval']
        self.safeties = self.config['safeties']
        self.checked_safeties = list(sorted(self.safeties.keys()))

        self.is_safe = self.make_data_stream('is_safe', 'int8', [len(self.safeties)], 20)

        self.make_property('checked_safeties', lambda: self.checked_safeties)

    def check_safety(self):
        current_time = get_timestamp()

        is_safes = np.zeros(len(self.safeties), dtype='int8')

        for i, safety_name in enumerate(self.checked_safeties):
            is_safe = True

            try:
                safety_info = self.safeties[safety_name]

                service = self.testbed.get_service(safety_info['service_name'])
                stream = service.get_data_stream(safety_info['stream_name'])

                last_frame = stream.get_latest_frame()

                # Check if frame is too old.
                timestamp_lower_bound = current_time - safety_info['safe_interval'] * 1e9
                if last_frame.timestamp < timestamp_lower_bound:
                    is_safe = False

                # Check value lower bound.
                if safety_info['minimum_value'] is not None:
                    if last_frame.data[0] < safety_info['minimum_value']:
                        is_safe = False

                # Check value upper bound.
                if safety_info['maximum_value'] is not None:
                    if last_frame.data[0] > safety_info['maximum_value']:
                        is_safe = False
            except Exception as e:
                self.log.error(f'Something happened during checking of safety "{safety_name}":')
                self.log.error(str(e))

                is_safe = False

            # Report if conditions are safe.
            is_safes[i] = is_safe

        # Submit safety.
        self.is_safe.submit_data(is_safes)

    def main(self):
        while not self.should_shut_down:
            start = time.time()

            self.check_safety()

            self.sleep(self.check_interval)

if __name__ == '__main__':
    service = SafetyMonitor()
    service.run()
