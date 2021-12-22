from catkit2.testbed.service import Service, parse_service_args
from catkit2.simulator.simulated_service import SimulatorClient

import time
import sys
import threading
import numpy as np

class CameraSim(Service):
    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'camera_sim', testbed_port)

        config = self.configuration

        self.simulator_connection = SimulatorClient(service_name, testbed_port)

    @property
    def

    def start_acquisition(self):
        self.simulator_connection.start_camera_acquisition(self.service_name, -1, self.exposure_time, self.frame_interval)

    def stop_acquisition(self):
        self.simulator_connection.end_camera_acquisition(self.service_name)
