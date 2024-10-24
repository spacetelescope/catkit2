'''
This module contains a service for Ocean Optics Spectrometers.
'''
import numpy as np

from seabreeze.spectrometers import Spectrometer
from seabreeze.spectrometers import SeaBreezeError

from catkit2.testbed.service import Service


class OceanOpticsSpectrometer(Service):
    '''
    Service for Ocean Optics Spectrometer.

    This service is a wrapper around the python seabreeze package.
    It provides a simple interface to control the spectrometer and acquire spectra.

    Attributes
    ----------
    spectrometer : Spectrometer
        The spectrometer to control.
    serial_number : str
        The serial number of the spectrometer.
    model : str
        The model of the spectrometer.
    pixels_number : int
        number of pixels in the spectrum.
    interval : float
        The interval between spectrum acquisitions in seconds.
    spectra : DataStream
        A data stream to submit spectra from the spectrometer.
    is_saturating : DataStream
        A data stream to submit whether the spectrometer is currently saturating.
    NUM_FRAMES : int
        The number of frames to allocate for the data streams.

    Methods
    -------
    open()
        Open the service.
    main()
        The main function of the service.
    close()
        Close the service.
    take_one_spectrum()
        Get a spectrum from the spectrometer.
    '''
    NUM_FRAMES = 20

    def __init__(self):
        '''
        Create a new OceanOpticsSpectrometer service.
        '''
        super().__init__('oceanoptics_spectrometer')

        self.serial_number = str(self.config['serial_number'])
        self.interval = self.config.get('interval', 1)
        self._exposure_time = self.config.get('exposure_time', 1000)

        self.spectrometer = None
        self.model = None
        self.pixels_number = None

    def open(self):
        '''
        Open the service.

        This function is called when the service is opened.
        It initializes the spectrometer and creates the data streams and properties.

        Raises
        ------
        ImportError
            If the spectrometer cannot be found.
        '''

        # Find the spectrometer
        try:
            self.spectrometer = Spectrometer.from_serial_number(self.serial_number)
        except SeaBreezeError:
            raise ImportError(f'OceanOptics: Could not find spectrometer with serial number {self.serial_number}')

        # exctract attributes
        self.model = self.spectrometer.model
        self.pixels_number = self.spectrometer.pixels

        # Define and set default exposure time.
        self.exposure_time = self._exposure_time

        # Create datastreams
        self.spectra = self.make_data_stream('spectra', 'float32', [self.pixels_number], self.NUM_FRAMES)

        self.is_saturating = self.make_data_stream('is_saturating', 'int8', [1], self.NUM_FRAMES)
        self.is_saturating.submit_data(np.array([0], dtype='int8'))

        # Create properties
        def make_property_helper(name, read_only=False):
            if read_only:
                self.make_property(name, lambda: getattr(self, name))
            else:
                self.make_property(name, lambda: getattr(self, name), lambda val: setattr(self, name, val))

        make_property_helper('exposure_time')
        make_property_helper('wavelengths', read_only=True)

    def main(self):
        '''
        The main function of the service.

        This function is called when the service is started.
        '''
        while not self.should_shut_down:
            intensities = self.take_one_spectrum()
            self.spectra.submit_data(np.array(intensities, dtype='float32'))

            if np.max(intensities) == self.spectrometer.max_intensity:
                self.is_saturating.submit_data(np.array([1], dtype='int8'))
            else:
                self.is_saturating.submit_data(np.array([0], dtype='int8'))

            self.sleep(self.interval)

    def take_one_spectrum(self):
        '''
        Measure and return one spectrum.
        '''
        return self.spectrometer.intensities()

    @property
    def wavelengths(self):
        '''
        The wavelengths of the spectrometer in nm.

        Returns:
        --------
        ndarray of float:
            wavelengths of the spectrometer.
        '''
        return self.spectrometer.wavelengths()

    @property
    def exposure_time(self):
        '''
        The exposure time in microseconds.

        Returns:
        --------
        int:
            The exposure time in microseconds.
        '''
        return self._exposure_time

    @exposure_time.setter
    def exposure_time(self, exposure_time: int):
        '''
        Set the exposure time in microseconds.

        This property can be used to set the exposure time of the spectrometer.

        If the `exposure_time` parameter is inferior to the minimum allowed exposure time for this
        spectrometer (set by Ocean Optics), it is set to the minimum allowed exposure time.
        If the `exposure_time` is larger than the maximum allowed exposure time, it is set to the
        maximum allowed exposure time.

        Parameters
        ----------
        exposure_time : int
            The exposure time in microseconds.
        '''
        int_time_range = self.spectrometer.integration_time_micros_limits
        if exposure_time < int_time_range[0]:
            exposure_time = int_time_range[0]
        if exposure_time > int_time_range[1]:
            exposure_time = int_time_range[1]

        self._exposure_time = exposure_time
        self.spectrometer.integration_time_micros(exposure_time)

    def close(self):
        '''
        Close the service.

        This function is called when the service is closed.
        It closes the spectrometer.
        '''
        self.spectrometer.close()
        self.spectrometer = None


if __name__ == '__main__':
    service = OceanOpticsSpectrometer()
    service.run()
