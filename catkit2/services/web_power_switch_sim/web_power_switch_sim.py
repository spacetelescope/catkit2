import threading

from catkit2.testbed.service import Service

class WebPowerSwitchSim(Service):
    def __init__(self):
        super().__init__('web_power_switch_sim')

        self.outlet_ids = self.config['outlets']

        self.outlets = {}
        for outlet_name in self.outlet_ids.keys():
            self.add_outlet(outlet_name)

    def add_outlet(self, outlet_name):
        self.outlets[outlet_name] = self.make_data_stream(outlet_name.lower(), 'int8', [1], 20)

    def monitor_outlet(self, outlet_name):
        while not self.should_shut_down:
            try:
                frame = self.outlets[outlet_name].get_next_frame(10)
            except Exception:
                # Timed out. This is used to periodically check the shutdown flag.
                continue

            # Turn the outlet on or off
            on = frame.data[0] != 0
            self.switch_outlet(outlet_name, on)

    def switch_outlet(self, outlet_name, on):
        outlet_id = self.outlet_ids[outlet_name]

        # Contact simulator.
        self.testbed.simulator.switch_power(outlet_name=outlet_name, powered=1 if on else 0)

    def open(self):
        # Start the outlet threads
        self.outlet_threads = {}

        for outlet_name in self.outlet_ids.keys():
            thread = threading.Thread(target=self.monitor_outlet, args=(outlet_name,))
            thread.start()

            self.outlet_threads[outlet_name] = thread

    def main(self):
        while not self.should_shut_down:
            self.sleep(1)

    def close(self):
        # Stop the outlet threads.
        for thread in self.outlet_threads.values():
            thread.join()

        self.outlet_threads = {}

if __name__ == '__main__':
    service = WebPowerSwitchSim()
    service.run()
