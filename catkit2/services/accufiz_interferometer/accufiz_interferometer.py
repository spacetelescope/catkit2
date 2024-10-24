import os
import h5py
import time
import requests
import uuid
import numpy as np
from scipy import ndimage
import math
from astropy.io import fits
from glob import glob
from catkit2.testbed.service import Service
import os
import threading


def rotate_and_flip_image(data, theta, flip):
    """
    Rotate and/or flip the image data.

    Parameters
    ----------
    data : numpy.ndarray
        Numpy array of image data.
    theta : int
        Rotation angle in degrees.
    flip : bool
        If True, flip the image horizontally.

    Returns
    -------
    numpy.ndarray
        Modified image after rotation and/or flip.
    """
    data_corr = np.rot90(data, int(theta / 90))

    if flip:
        data_corr = np.fliplr(data_corr)

    return data_corr


class AccufizInterferometer(Service):
    """
    Service class for the 4D Technologies Accufiz Interferometer.
    It handles image acquisition, processing, and data handling.
    This requires 4D Insight Web Service to be running, and the 4Sight software to be set to listening.
    """
    NUM_FRAMES_IN_BUFFER = 20
    instrument_lib = requests

    def __init__(self):
        """
        Initialize the Accufiz Interferometer Simulator with configuration and set up data streams.
        """
        super().__init__('accufiz_interferometer')

        # Essential configurations
        self.mask = self.config['mask']
        self.server_path = self.config['server_path']
        self.local_path = self.config['local_path']

        # Optional configurations
        self.ip = self.config.get('ip_address', 'localhost:8080')
        self.calibration_data_package = self.config.get('calibration_data_package', '')
        self.timeout = self.config.get('timeout', 10000)
        self.post_save_sleep = self.config.get('post_save_sleep', 1)
        self.file_mode = self.config.get('file_mode', True)
        self.image_height = self.config.get('height', 1967)
        self.image_width = self.config.get('width', 1970)
        self.config_id = self.config.get('config_id', 'accufiz')
        self.save_h5 = self.config.get('save_h5', True)
        self.save_fits = self.config.get('save_fits', False)
        self.num_frames_avg = self.config.get('num_avg', 2)
        self.fliplr = self.config.get('fliplr', True)
        self.rotate = self.config.get('rotate', 0)

        # Set the 4D timeout.
        self.html_prefix = f"http://{self.ip}/WebService4D/WebService4D.asmx"
        set_timeout_string = f"{self.html_prefix}/SetTimeout?timeOut={self.timeout}"
        self.get(set_timeout_string)

        # Set the mask
        self.set_mask()

        # Create data streams.
        self.detector_masks = self.make_data_stream('detector_masks', 'uint8', [self.image_height, self.image_width], self.NUM_FRAMES_IN_BUFFER)
        self.images = self.make_data_stream('images', 'float32', [self.image_height, self.image_width], self.NUM_FRAMES_IN_BUFFER)
        self.is_acquiring = self.make_data_stream('is_acquiring', 'int8', [1], 20)
        self.is_acquiring.submit_data(np.array([0], dtype='int8'))
        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.clear()

        self.make_command('take_measurement', self.take_measurement)
        self.make_command('start_acquisition', self.start_acquisition)
        self.make_command('end_acquisition', self.end_acquisition)

    def set_mask(self):
        """
        Set the mask for the simulator. The mask must be local to the 4D computer in a specified directory.

        Returns
        -------
        bool
            True if the mask is successfully set.
        """
        filemask = self.mask
        typeofmask = "Detector"
        parammask = {"maskType": typeofmask, "fileName": filemask}
        set_mask_string = f"{self.html_prefix}/SetMask"

        self.post(set_mask_string, data=parammask)

        return True

    def get(self, url, params=None, **kwargs):
        """
        HTTP GET request.

        Parameters
        ----------
        url : str
            URL to send the GET request to.
        params : dict, optional
            Parameters for the request. Defaults to None.

        Returns
        -------
        resp
            Response object.

        Raises
        ------
        RuntimeError
            If the GET request fails.
        """
        resp = self.instrument_lib.get(url, params=params, **kwargs)
        if resp.status_code != 200:
            raise RuntimeError(f"{self.config_id} GET error: {resp.status_code}: {resp.text}")
        return resp

    def post(self, url, data=None, json=None, **kwargs):
        """
        HTTP POST request.

        Parameters
        ----------
        url : str
            URL to send the POST request to.
        data : dict, optional
            Data to send in the request. Defaults to None.
        json : dict, optional
            JSON data to send in the request. Defaults to None.

        Returns
        -------
        resp
            Response object.

        Raises
        ------
        RuntimeError
            If the POST request fails.
        """
        resp = self.instrument_lib.post(url, data=data, json=json, **kwargs)
        if resp.status_code != 200:
            raise RuntimeError(f"{self.config_id} POST error: {resp.status_code}: {resp.text}")
        time.sleep(self.post_save_sleep)
        return resp

    def take_measurement(self):
        """
        Take a measurement, save the data, and return the processed image.

        Returns
        -------
        numpy.ndarray
            Processed image data after measurement.

        Raises
        ------
        RuntimeError
            If data acquisition or saving fails.
        """
        # Send request to take data.
        resp = self.post(f"{self.html_prefix}/AverageMeasure", data={"count": int(self.num_frames_avg)})

        if "success" not in resp.text:
            raise RuntimeError(f"{self.config_id}: Failed to take data - {resp.text}.")

        filename = str(uuid.uuid4())
        server_file_path = os.path.join(self.server_path, filename)
        local_file_path = os.path.join(self.local_path, filename)

        # This line is here because when sent through webservice slashes tend
        # to disappear. If we sent in parameter a path with only one slash,
        # they disappear
        server_file_path = server_file_path.replace('\\', '/')
        server_file_path = server_file_path.replace('/', '\\\\')

        # Send request to save data.
        self.post(f"{self.html_prefix}/SaveMeasurement", data={"fileName": server_file_path})

        if not glob(f"{local_file_path}.h5"):
            raise RuntimeError(f"{self.config_id}: Failed to save measurement data to '{local_file_path}'.")

        local_file_path = local_file_path if local_file_path.endswith(".h5") else f"{local_file_path}.h5"
        self.log.info(f"{self.config_id}: Succeeded to save measurement data to '{local_file_path}'")

        mask = np.array(h5py.File(local_file_path, 'r').get('measurement0').get('Detectormask', 1))
        img = np.array(h5py.File(local_file_path, 'r').get('measurement0').get('genraw').get('data')) * mask

        self.detector_masks.submit_data(mask.astype(np.uint8))

        image = self.convert_h5_to_fits(local_file_path, rotate=self.rotate, fliplr=self.fliplr, mask=mask, img=img, create_fits=self.save_fits)

        # Remove HDF5 file if not required
        if (not self.save_h5) and os.path.exists(local_file_path):
            os.remove(local_file_path)

        return image

    @staticmethod
    def convert_h5_to_fits(filepath, rotate, fliplr, img, mask, wavelength=632.8, create_fits=False):
        """
        Convert HDF5 data to FITS format and process image data.

        Parameters
        ----------
        filepath : str
            Filepath for the HDF5 data.
        rotate : int
            Rotation angle in degrees.
        fliplr : bool
            If True, flip the image horizontally.
        img : numpy.ndarray
            Image data to be processed.
        mask : numpy.ndarray
            Mask data to be applied.
        wavelength : float, optional
            Wavelength for scaling, default is 632.8 nm.
        create_fits : bool, optional
            If True, save the processed image as a FITS file.

        Returns
        -------
        numpy.ndarray
            Processed image data.
        """
        filepath = filepath if filepath.endswith(".h5") else f"{filepath}.h5"
        fits_filepath = f"{os.path.splitext(filepath)[0]}.fits"

        mask = np.array(h5py.File(filepath, 'r').get('measurement0').get('Detectormask', 1))
        img = np.array(h5py.File(filepath, 'r').get('measurement0').get('genraw').get('data')) * mask

        if create_fits:
            fits.PrimaryHDU(mask).writeto(fits_filepath, overwrite=True)

        radiusmask = np.int64(np.sqrt(np.sum(mask) / math.pi))
        center = ndimage.measurements.center_of_mass(mask)

        image = np.clip(img, -10, +10)[
            np.int64(center[0]) - radiusmask:np.int64(center[0]) + radiusmask - 1,
            np.int64(center[1]) - radiusmask:np.int64(center[1]) + radiusmask - 1
        ]

        # Apply the rotation and flips.
        image = rotate_and_flip_image(image, rotate, fliplr)

        # Convert waves to nanometers.
        image = image * wavelength

        if create_fits:
            fits_hdu = fits.PrimaryHDU(image)
            fits_hdu.writeto(fits_filepath, overwrite=True)

        return image

    def main(self):
        """
        Main loop to manage data acquisition and processing.
        """
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.acquisition_loop()

    def acquisition_loop(self):
        """
        Handle continuous data acquisition while the service is running.
        """
        try:
            self.is_acquiring.submit_data(np.array([1], dtype='int8'))

            while self.should_be_acquiring.is_set() and not self.should_shut_down:
                img = self.take_measurement()

                has_correct_parameters = np.allclose(self.images.shape, img.shape)

                if not has_correct_parameters:
                    self.images.update_parameters('float32', img.shape, 20)

                self.images.submit_data(img.astype('float32'))
                time.sleep(0.05)
        finally:
            self.is_acquiring.submit_data(np.array([0], dtype='int8'))

    def start_acquisition(self):
        """
        Start the data acquisition process.
        """
        self.should_be_acquiring.set()

    def end_acquisition(self):
        """
        End the data acquisition process.
        """
        self.should_be_acquiring.clear()


if __name__ == '__main__':
    service = AccufizInterferometer()
    service.run()
