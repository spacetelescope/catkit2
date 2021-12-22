import time
import sys
import threading

import requests
import numpy as np

from catkit2.testbed.service import Service, parse_service_args

class WebPowerSwitch(Service):
    _OK_STATES = (7, 11, 12, 42)

    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'web_power_switch', testbed_port)

        config = self.configuration
        self.user = config['user']
        self.password = config['password']
        self.ip_address = config['ip_address']
        self.dns = config['dns']

        self.outlet_ids = config['outlets']

        self.shutdown_flag = threading.Event()

        self.outlets = {}
        for outlet_name in self.outlet_ids.keys():
            self.add_outlet(outlet_name)

    def add_outlet(self, outlet_name):
        self.outlets[outlet_name] = self.make_data_stream(outlet_name, 'int8', [1], 20)

    def monitor_outlet(self, outlet_name):
        while not self.shutdown_flag.is_set():
            try:
                frame = self.outlets[outlet_name].get_next_frame(10)
            except:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            # Turn the outlet on or off
            on = frame.data[0] != 0
            self.switch_outlet(outlet_name, on)

    def switch_outlet(self, outlet_name, on):
        outlet_id = self.outlet_ids[outlet_name]

        script_line = outlet_id * 4 if on else outlet_id * 4 - 2
        ip_string = f'http://{self.ip_address}/script?run{script_line:03d}=run'

        response = requests.get(ip_string, auth=(self.user, self.password))
        response.raise_for_status()

        if response.status_code != 200:
            raise RuntimeError(f'GET returned {response.status_code} when 200 was expected.')

    def open(self):
        # Start the outlet threads
        self.outlet_threads = {}

        for outlet_name in self.outlet_ids.keys():
            thread = threading.Thread(target=self.monitor_outlet, args=(outlet_name,))
            thread.start()

            self.outlet_threads[outlet_name] = thread

    def main(self):
        self.shutdown_flag.wait()

    def close(self):
        # Stop the outlet threads
        self.shutdown_flag.set()

        for thread in self.outlet_threads.values():
            thread.join()

        self.outlet_threads = {}

    def shut_down(self):
        self.shutdown_flag.set()

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = WebPowerSwitch(service_name, testbed_port)
    service.run()
