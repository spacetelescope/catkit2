'''
This module contains a service for Ocean Optics Spectrometers.
'''

import threading

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
    wavelengths : NDArray[numpy.float_]
        A NDArray with the wl of the spectrometer.
    spectra : DataStream
        A data stream to submit spectra from the spectrometer.
    should_be_acquiring : threading.Event
        An event to signal whether the spectrometer should acquire a spectrum.
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
    start_acquisition()
        Start the acquisition.
    take_one_spectrum()
        Get a spectrum from the spectrometer.
    exposure_time()
        Set the exposure time of the spectrometer.

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

        self.wavelengths = None
        self.spectra = None

        self._exposure_time = None

        self.should_be_acquiring = threading.Event()
        self.should_be_acquiring.set()

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
        self.wavelengths = self.spectrometer.wavelengths()

        # Define and set defaut exposure time
        self._exposure_time = self.config.get('exposure_time', 1000)
        self.exposure_time(self._exposure_time)

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.spectra = self.make_data_stream('spectra', 'float32', [self.pixels_number], self.NUM_FRAMES)

    def main(self):
        '''
        The main function of the service.

        This function is called when the service is started.
        '''
        while not self.should_shut_down:
            if self.should_be_acquiring.wait(0.05):
                self.take_one_spectrum()
                self.end_acquisition()

    def start_acquisition(self):
        '''
        Start the acquisition loop.
        '''
        self.should_be_acquiring.set()

    def end_acquisition(self):
        '''
        End the acquisition loop.
        '''
        self.should_be_acquiring.clear()

    def take_one_spectrum(self):
        '''
        measure one spectrum and submit it to the data stream.
        '''
        self.spectra.submit_data(self.spectrometer.intensities(), dtype='float32')

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
        if exposure_time < int_time_range[0] or exposure_time > int_time_range[1]:
            raise ValueError(
                f"OceanOptics: integration time need to be in [{int_time_range[0]}, {int_time_range[1]}] range (ms)")

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
