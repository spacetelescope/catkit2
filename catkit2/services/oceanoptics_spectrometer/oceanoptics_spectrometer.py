'''
This module contains a service for Ocean Optics Sectrometer

This service is a wrapper around the python seabreeze package
It provides a simple interface to control the spectro and acquire spectras.
'''

from catkit2.testbed.service import Service

from seabreeze.spectrometers import Spectrometer as spct
from seabreeze.spectrometers import SeabreezeError

class OceanOpticsSpectrometer(Service):
    '''
    Service for Ocean Optics Spectrometer.

    This service is a wrapper around the python seabreeze package
    It provides a simple interface to control the spectro and acquire spectras.

    Attributes
    ----------
    spectrometer : Spectrometer
        The spectrometer to control.
    model : str
        The model of the spectrometer.
    pixels_number : int
        number of pix in the spectras
    wavelengths : NDArray[numpy.float_]
        A NDArray with the wl of the spectrometer.
    spectras : DataStream
        A data stream to submit the spectras from the spectrometer.
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
    get_spectra()
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

        self.spectrometer = None
        self.model = None
        self.pixels_number = None

        self.wavelengths = None
        self.spectras = None

    def open(self):
        '''
        Open the service.

        This function is called when the service is opened.
        It initializes the spectrometer and creates the data streams and properties.

        Raises
        ------
        RuntimeError
            If the spectro cannot be found.

        '''

        # Find the spectrometer
        self.serial_number = str(self.config['serial_number'])

        try:
            self.spectrometer = spct.from_serial_number(self.serial_number)
        except SeabreezeError:
            raise ImportError(f'OceanOptics: Could not find spectrometer with serial number {self.serial_number}')

        # Set the exposure time
        self.exposure_time = self.config.get('exposure_time', 1000)
        self.make_property('exposure_time', lambda: getattr(self, 'exposure_time'),
                           lambda val: setattr(self, 'exposure_time', val))

        # exctract attributes
        self.model = self.spectrometer.model
        self.pixels_number = self.spectrometer.pixels
        self.wavelengths = self.spectrometer.wavelengths()

        # Create datastreams
        # Use the full sensor size here to always allocate enough shared memory.
        self.spectras = self.make_data_stream('spectras', 'float32', self.pixels_number, self.NUM_FRAMES)

    def main(self):
        '''
        The main function of the service.

        This function is called when the service is started.
        '''
        while not self.should_shut_down:
            self.get_spectra()

    def get_spectra(self):
        spectra = self.spectrometer.intensities() 
        self.spectras.submit_data(spectra, dtype='float32')
 
    @exposure_time.setter
    def exposure_time(self, exposure_time: int):
        '''
        Set the exposure time in microseconds.

        This property can be used to set the exposure time of the spectr0.

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

        self.spectrometer.integration_time_micros(exposure_time)

    def close(self):
        '''
        Close the service.

        This function is called when the service is closed.
        It close the spectro loop and cleans up the data streams.
        '''
        self.spectrometer.close()
        self.spectrometer = None


if __name__ == '__main__':
    service = OceanOpticsSpectrometer()
    service.run()
