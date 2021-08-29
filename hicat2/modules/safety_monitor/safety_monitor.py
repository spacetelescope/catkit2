from hicat2.bindings import Module, DataStream, Command, Property, get_timestamp
from hicat2.testbed import parse_module_args

import time
import sys

class SafetyMonitorModule(Module):
    def __init__(self):
        args = parse_module_args()
        Module.__init__(self, args.module_name, args.module_port)

        self.testbed = Testbed(args.testbed_server_port)
        config = self.testbed.config['modules'][args.module_name]

        self.check_interval = config['check_interval']
        self.safeties = config['safeties']
        self.checked_safeties = list(sorted(self.safeties.keys()))

        self.shutdown_flag = False

        self.data_streams = {}

        self.is_safe = DataStream.create('is_safe', self.name, 'int8', [len(self.safeties)], 20)
        self.register_data_stream(self.is_safe)

        self.register_property(Property('checked_safeties', lambda: return self.checked_safeties))

    def check_safety(self):
        frame = self.is_safe.request_new_frame()
        current_time = get_timestamp()

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
            frame.data[i] = is_safe

        # Submit safety.
        self.is_safe.submit_frame(frame.id)

    def open(self):
        for safety_name in self.checked_safeties:
            safety = self.safeties[safety_name]

            module = getattr(self.testbed, safety['module_name'])
            self.data_streams[safety_name] = getattr(module, safety['stream_name'])

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
