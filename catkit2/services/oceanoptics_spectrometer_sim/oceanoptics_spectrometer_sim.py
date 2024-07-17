'''
This module contains a service for simulation Ocean Optics Spectrometers.
'''
import numpy as np
from catkit2.testbed.service import Service


class OceanOpticsSpectrometerSim(Service):
    '''
    Service for simulated Ocean Optics Spectrometer.

    Attributes
    ----------
    spectrometer : Spectrometer
        The spectrometer to control.
    serial_number : str
        The serial number of the spectrometer.
    pixels_number : int
        Number of pixels in the spectrum.
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
        super().__init__('oceanoptics_spectrometer_sim')

        self.serial_number = str(self.config['serial_number'])
        self.interval = self.config.get('interval', 1)
        self._exposure_time = self.config.get('exposure_time', 1000)


        self.pixels_number = 3000

        self.spectra = None
        self.is_saturating = None

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

        # Define and set defaut exposure time
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
            intensities = self.take_one_spectrum(self.pixels_number)
            self.spectra.submit_data(np.array(intensities, dtype='float32'))
            self.is_saturating.submit_data(np.array([0], dtype='int8'))

            self.sleep(self.interval)

    def take_one_spectrum(self):
        '''
        Measure and return one spectrum.
        Simulated service: random numpy array.
        '''
        return np.random.random(self.pixels_number) + 1000

    @property
    def wavelengths(self):
        '''
        The wavelengths of the spectrometer in nm.
        Simulated service: linear vector evenly spaced bewtween 350 and 1000 nm.

        Returns:
        --------
        ndarray of float:
            wavelengths of the spectrometer.
        '''
        return np.linspace(350, 1000, num=self.pixels_number)

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

        Parameters
        ----------
        exposure_time : int
            The exposure time in microseconds.
        '''
        self._exposure_time = exposure_time


if __name__ == '__main__':
    service = OceanOpticsSpectrometerSim()
    service.run()
