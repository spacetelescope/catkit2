import threading
import time
import os
import numpy as np

from catkit2.testbed.service import Service

from vimba import *



class AlliedVisionCamera(Service):

    NUM_FRAMES = 20


    def __init__(self):
        super().__init__('AlliedVision_camera')

        self.should_be_aquiring = threading.Event()
        self.should_be_aquiring.set()

        self.mutex = threading.Lock()


