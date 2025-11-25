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
import csv
import json


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
        self.new_software = self.config.get('new_software', False)

        # Set the 4D timeout.
        if self.new_software:
            self.html_prefix = f"http://{self.ip}"
        else:
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

        if self.new_software:
            set_mask_string = f"{self.html_prefix}/SystemService/SetDetectorMask"
            self.post(set_mask_string, json={"Mask": filemask})
        else:
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
        if self.new_software:
            resp = self.get(f"{self.html_prefix}/SystemService/TakeAveragedMeasurement?numberOfSamples={self.num_frames_avg}")
        else:
            resp = self.post(f"{self.html_prefix}/AverageMeasure", data={"count": int(self.num_frames_avg)})

        if not self.new_software and "success" not in resp.text:
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
        if self.new_software:
            data = server_file_path + ".csv"
            dumped_data = json.dumps(data)
            encoded_data = dumped_data.encode('utf-8')
            self.post(f"{self.html_prefix}/DataService/SaveDataToDisk/", data=encoded_data, headers={'Content-type': 'application/json'})

        else:
            self.post(f"{self.html_prefix}/SaveMeasurement", data={"fileName": server_file_path})

        if not glob(f"{local_file_path}.h5") and not glob(f"{local_file_path}.csv"):
            raise RuntimeError(f"{self.config_id}: Failed to save measurement data to '{local_file_path}'.")

        if self.new_software:
            local_file_path = local_file_path if local_file_path.endswith(".csv") else f"{local_file_path}.csv"
        else:
            local_file_path = local_file_path if local_file_path.endswith(".h5") else f"{local_file_path}.h5"
            mask = np.array(h5py.File(local_file_path, 'r').get('measurement0').get('Detectormask', 1))
            img = np.array(h5py.File(local_file_path, 'r').get('measurement0').get('genraw').get('data')) * mask

        self.log.info(f"{self.config_id}: Succeeded to save measurement data to '{local_file_path}'")

        # self.detector_masks.submit_data(mask.astype(np.uint8))
        if self.new_software:
            image = self.convert_csv_to_fits(local_file_path, rotate=self.rotate, fliplr=self.fliplr, create_fits=self.save_fits)
        else:
            image = self.convert_h5_to_fits(local_file_path, rotate=self.rotate, fliplr=self.fliplr, mask=mask, img=img, create_fits=self.save_fits)

        # Remove HDF5 or CSV file if not required
        if (not self.save_h5) and os.path.exists(local_file_path):
            os.remove(local_file_path)

        return np.ascontiguousarray(image)

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

    @staticmethod
    def convert_csv_to_fits(filepath, rotate, fliplr, wavelength=632.8,
                            create_fits=False):
        """
        Convert CSV data to FITS format and process image data.

        Parameters
        ----------
        filepath : str
            Filepath for the CSV data.
        rotate : int
            Rotation angle in degrees.
        fliplr : bool
            If True, flip the image horizontally.
        wavelength : float, optional
            Wavelength for scaling, default is 632.8 nm.
        create_fits : bool, optional
            If True, save the processed image as a FITS file.

        Returns
        -------
        numpy.ndarray
            Processed image data.
        """
        filepath = filepath if filepath.endswith(".csv") else f"{filepath}.csv"
        fits_filepath = f"{os.path.splitext(filepath)[0]}.fits"

        image = []
        with open(filepath, 'r') as csvfile:
            reader = csv.reader(csvfile)
            header_dict = {}

            # Iterate over each row in the CSV file
            for i, row in enumerate(reader):
                final_row = []
                # First 12 rows contain header information.
                if i < 12:
                    try:
                        hkey, _, hval = row[0].partition(': ')
                        header_dict[hkey] = float(hval)
                    except ValueError:
                        header_dict[hkey] = hval
                    except IndexError:
                        pass
                else:
                    for item in row:
                        try:
                            final_row.append(float(item.strip()))
                        except ValueError:
                            final_row.append(np.nan)
                    image.append(final_row)

            image = np.array(image)

            # Remove all masked rows and columns (NaNs)
            mask_rows = np.all(np.isnan(image), axis=1)
            image = image[~mask_rows]

            mask_cols = np.all(np.isnan(image), axis=0)
            image = image[:, ~mask_cols]

            # Apply the rotation and flips.
            image = rotate_and_flip_image(image, rotate, fliplr)

            # Convert waves to nanometers.
            image = image * wavelength

            if create_fits:
                hdu = fits.PrimaryHDU(data=image)
                for key, value in header_dict.items():
                    try:
                        hdu.header[key.capitalize()[:8]] = value
                    except ValueError:
                        hdu.header[key.capitalize()[:8]] = str(value)

                hdu.writeto(fits_filepath, overwrite=True)

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
