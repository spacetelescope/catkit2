import os
import h5py
import time
import requests
import uuid
import numpy as np
from glob import glob
from catkit2.testbed.service import Service

LOCAL_PATH = ""
SERVER_PATH = ""


class Accufiz(Service):
    NUM_FRAMES_IN_BUFFER = 20

    def __init__(self):
        super().__init__('accufiz_interferometer')

        self.ip = self.config.get('ip_address', 0)
        self.timeout = self.config.get('timeout', 60)
        self.html_prefix = f"http://{self.ip}/WebService4D/WebService4D.asmx"
        self.mask = self.config.get('mask', "dm2_detector.mask")
        self.post_save_sleep = self.config.get('post_save_sleep', 1)
        self.file_mode = self.config.get('file_mode', True)
        self.calibration_data_package = self.config.get('calibration_data_package', "")
        self.image_height = self.config.get('height', 509)
        self.image_width = self.config.get('width', 509)

        # Set the 4D timeout.
        set_timeout_string = f"{self.html_prefix}/SetTimeout?timeOut={self.timeout}"
        self.get(set_timeout_string)

        # Create data streams.
        self.detector_masks = self.make_data_stream('detector_masks', 'float32', [self.image_height, self.image_width], self.NUM_FRAMES_IN_BUFFER)
        self.images = self.make_data_stream('images', 'float32', [self.image_height, self.image_width], self.NUM_FRAMES_IN_BUFFER)

    instrument_lib = requests

    def open(self):
        # Set the Mask. This mask has to be local to the 4D computer in this directory.
        filemask = os.path.join("c:\\4Sight_masks", self.mask)
        typeofmask = "Detector"
        parammask = {"maskType": typeofmask, "fileName": filemask}
        set_mask_string = "http://{}/WebService4D/WebService4D.asmx/SetMask".format(self.ip)

        requests.post(set_mask_string, data=parammask)

        return True

    def get(self, url, params=None, **kwargs):
        resp = self.instrument_lib.get(url, params=params, **kwargs)
        if resp.status_code != 200:
            raise RuntimeError(f"{self.config_id} GET error: {resp.status_code}: {resp.text}")
        return resp

    def post(self, url, data=None, json=None, **kwargs):
        resp = self.instrument_lib.post(url, data=data, json=json, **kwargs)
        if resp.status_code != 200:
            raise RuntimeError(f"{self.config_id} POST error: {resp.status_code}: {resp.text}")
        time.sleep(self.post_save_sleep)
        return resp

    def take_measurement(self, num_frames=2):
        # Send request to take data.
        resp = self.post(f"{self.html_prefix}/AverageMeasure", data={"count": int(num_frames)})
        if "success" not in resp.text:
            raise RuntimeError(f"{self.config_id}: Failed to take data - {resp.text}.")

        filename = str(uuid.uuid4())
        server_file_path = os.path.join(self.server_path, filename)
        local_file_path = os.path.join(self.local_path, filename)

        #  This line is here because when sent through webservice slashes tend
        #  to disappear. If we sent in parameter a path with only one slash,
        #  they disappear
        server_file_path = server_file_path.replace('\\', '/')
        server_file_path = server_file_path.replace('/', '\\\\')

        # Send request to save data.
        self.post(f"{self.html_prefix}/SaveMeasurement", data={"fileName": server_file_path})

        if not glob(f"{local_file_path}.h5"):
            raise RuntimeError(f"{self.config_id}: Failed to save measurement data to '{local_file_path}'.")

        self.log.info(f"{self.config_id}: Succeeded to save measurement data to '{local_file_path}'")

        maskinh5 = np.array(h5py.File(local_file_path, 'r').get('measurement0').get('Detectormask'))
        image0 = np.array(h5py.File(local_file_path, 'r').get('measurement0').get('genraw').get('data')) * maskinh5

        self.detector_masks.submit_data(maskinh5, dtype='float32')
        self.images.submit_data(image0, dtype='float32')

        return maskinh5, image0
