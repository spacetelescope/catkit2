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
        number of pix in the spectrum.
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

        self.serial_number = None
        self.spectrometer = None
        self.model = None
        self.pixels_number = None

        self.spectra = None
        self.is_saturating = None

        self.interval = self.config.get('interval', 1)

        self._exposure_time = None

    def open(self):
        '''
        Open the service.

        This function is called when the service is opened.
        It initializes the spectrometer and creates the data streams and properties.

        Raises
        ------
        RuntimeError
            If the spectrometer cannot be found.
        '''

        # Find the spectrometer
        self.serial_number = str(self.config['serial_number'])
        try:
            self.spectrometer = Spectrometer.from_serial_number(self.serial_number)
        except SeaBreezeError:
            raise ImportError(f'OceanOptics: Could not find spectrometer with serial number {self.serial_number}')

        # exctract attributes
        self.model = self.spectrometer.model
        self.pixels_number = self.spectrometer.pixels

        # Define and set defaut exposure time
        self._exposure_time = self.config.get('exposure_time', 1000)
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
            self.sleep(self.interval)

    def take_one_spectrum(self):
        '''
        Measure one spectrum and submit it to the data stream.
        '''
        intensities = self.spectrometer.intensities()

        if np.max(intensities) ==  self.spectrometer.max_intensity:
            self.is_saturating.submit_data(np.array([1], dtype='int8'))
        else:
            self.is_saturating.submit_data(np.array([0], dtype='int8'))

        return intensities

    @property
    def wavelengths(self):
        '''
        The wavelengths of the spectrometer.

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
        if exposure_time < min allowed exp time: exposure_time =  min allowed exp time
        if exposure_time > max allowed exp time: exposure_time =  max allowed exp time

        Parameters
        ----------
        exposure_time : int
            The exposure time in microseconds.

        Raises
        ------
        ValueError
            If the exposure time is not in the range of the accepted spectrometer values.
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
        It close the spectrometer and cleans up the data streams.
        '''
        self.spectrometer.close()
        self.spectrometer = None


if __name__ == '__main__':
    service = OceanOpticsSpectrometer()
    service.run()
