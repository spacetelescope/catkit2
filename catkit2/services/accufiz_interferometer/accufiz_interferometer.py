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
from restart_4sight import Restart4SightWebService


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

        # diagnostic
        self.alive_frames = 0
        self.alive_time = None

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
        self.binning = self.config.get('binning', 1)
        self.circular_crop = self.config.get('circular_crop', True)
        self.log.info(f'Set binning to {self.binning}')

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

        # Create properties
        def make_property_helper(name, read_only=False, requires_stopped_acquisition=False):
            if read_only:
                self.make_property(name, lambda: getattr(self, name))
            else:
                def setter(val):
                    setattr(self, name, val)

                self.make_property(name, lambda: getattr(self, name), setter)

        make_property_helper('folder')

    @property
    def folder(self):
        return self.local_path

    @folder.setter
    def folder(self, newfolder):
        self.server_path = newfolder
        self.local_path = newfolder

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

        resp = self.post(set_mask_string, data=parammask)

        self.log.info(f'loaded mask {filemask} resp {resp.text}')

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
        max_attempts = 3
        num_attempts = 0
        successful = False
        img = None
        while (num_attempts < max_attempts) and (not successful):
            try:
                num_attempts += 1
                img = self._take_measurement()
                successful = True
            except KeyboardInterrupt as k:
                raise k
            except Exception as e:
                self.log.error(f'Attempt {num_attempts}. encountered issue {e} will try to restart the server and try again', exc_info=True)
                hours = (time.time() - self.alive_time)/(60*60)
                self.testbed.watchdog.send_diagnostic(message=f'Attempt {num_attempts}. encountered issue {e} will try to restart the 4sight server and try again...'
                                                      + f'\n\nTotal frames taken = {self.alive_frames}, alive {hours:.2f} hours')
                proc = Restart4SightWebService()
                proc.perform_restart()
                time.sleep(15)
                resp = self.post(f"{self.html_prefix}/AverageMeasure",
                data= {"count": int(self.num_frames_avg)})
                if "success" in resp.text:
                    self.log.info('Test image successful!')
                else:
                    self.log.info(f"failed to take 4D measurement attempt")
                self.alive_frames = 0
                self.alive_time = time.time()

        if not successful:
            raise Exception(f'restarted 4sight web service {max_attempts} and was not able to get images')
        
        has_correct_parameters = np.allclose(self.images.shape, img.shape)

        if not has_correct_parameters:
            self.images.update_parameters('float32', img.shape, 20)

        self.images.submit_data(img.astype('float32'))
        
        return img

    def _take_measurement(self):
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
        if self.alive_time is None:
            self.alive_time = time.time()
        num_tries = 0
        successful_measurement = False
        while (num_tries < 3) and (not successful_measurement):
            num_tries += 1
            # Send request to take data.
            resp = self.post(f"{self.html_prefix}/AverageMeasure",
                            data={"count": int(self.num_frames_avg)})
            if "success" in resp.text:
                successful_measurement = True
            else:
                self.log.info(f"failed to take 4D measurement attempt {num_tries}")
                time.sleep(1)

        if not successful_measurement:
            raise RuntimeError(
                f"{self.config_id}: Failed to take data - {resp.text}.")

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

        num_tries = 0
        successful_read = False
        while (num_tries < 2) and (not successful_read):
            try:
                num_tries += 1
                mask = np.array(h5py.File(local_file_path, 'r').get('measurement0').get('Detectormask', 1))
                # LM - mask not matching new image size. I wonder if we should have an option to disable the mask instead
                if self.circular_crop:
                    img = np.array(h5py.File(local_file_path, 'r').get('measurement0').get('genraw').get('data')) * mask
                else:
                    # The detector mask key is not loaded and does not match the size of the 1/4 image
                    img = np.array(h5py.File(local_file_path, 'r').get('measurement0').get('genraw').get('data'))
                    img[img > 65000] = np.nan

                    # When operating in 1/4 resolution mode, the image returned by the 4D is 491 x 492 pixels (Not square!). 
                    # Since the last column is all NaNs in this case, we just trim it out manually,  
                    # because having a non-square image turns out to cause a ripple effect of problems later, otherwise. 
                    if (img.shape[0] == 491) and (img.shape[1] == 492):
                        img = img[:,:-1]
    
                # if we get here we have successfully read the data
                successful_read = True
            except Exception as e:
                self.log.info(f'{e} - failed to read data out of file. Maybe it is still writing... trying again')
                time.sleep(1)

        # Make sure the data stream has the right size and datatype.
        self.log.info(str(mask.shape))
        print(mask)
        if mask.shape == ():
            mask = np.ones((self.image_height, self.image_width), dtype=np.uint8)
            print(mask)
    
        has_correct_parameters = np.allclose(mask.shape, [self.image_height, self.image_width]) 
        
        if not has_correct_parameters:
            self.image_height = mask.shape[0]
            self.image_width = mask.shape[1]
            self.detector_masks.update_parameters('uint8', [self.image_height, self.image_width], self.NUM_FRAMES_IN_BUFFER)

        self.detector_masks.submit_data(mask.astype(np.uint8))

        image = self.convert_h5_to_fits(local_file_path, rotate=self.rotate,
                                        fliplr=self.fliplr, mask=mask, img=img, create_fits=self.save_fits,
                                        binning=self.binning, circular_crop=self.circular_crop)

        # Remove HDF5 file if not required
        if (not self.save_h5) and os.path.exists(local_file_path):
            os.remove(local_file_path)

        self.alive_frames += 1


        return np.ascontiguousarray(image, dtype=np.float32)
    

    @staticmethod
    def convert_h5_to_fits(filepath, rotate, fliplr, img, mask, wavelength=632.8, create_fits=False, binning=1, circular_crop=True):
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


        if create_fits:
            fits.PrimaryHDU(mask).writeto(fits_filepath, overwrite=True)
        
        if circular_crop:
            radiusmask = np.int64(np.sqrt(np.sum(mask) / math.pi))
            center = ndimage.measurements.center_of_mass(mask)

            image = np.clip(img, -10, +10)[
                np.int64(center[0]) - radiusmask:np.int64(center[0]) + radiusmask - 1,
                np.int64(center[1]) - radiusmask:np.int64(center[1]) + radiusmask - 1
            ]
        else:
            image = img

        # Apply the rotation and flips.
        image = rotate_and_flip_image(image, rotate, fliplr)

        # Convert waves to nanometers.
        image = image[::binning, ::binning] * wavelength

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
