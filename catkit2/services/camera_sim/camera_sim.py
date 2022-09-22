from catkit2.testbed.service import Service
from catkit2.simulator.simulated_service import SimulatorClient

import time
import sys
import threading
import numpy as np

class CameraSim(Service):
    def __init__(self):
        super().__init__('camera_sim')
