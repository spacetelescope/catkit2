from catkit2.simulator import SimpleOpticalModel, Simulator
import hcipy
import numpy as np


class SimpleSimulator(Simulator):
    '''A simple simulator for the SimpleOpticalModel.

    This service is not meant to be used, but rather serves as an
    example on how to use the Simulator base class.
    '''
    def __init__(self):
        super().__init__('simple_simulator')

        self.alpha = 1

    def open(self):
        self.model = SimpleOpticalModel()
        wavefronts = [hcipy.Wavefront(self.model.pupil_grid.ones() * 1e6)]
        self.model.set_wavefronts('pre_pupil', wavefronts)

        self.update_atmosphere()

    def actuate_dm(self, at_time, dm_name, new_actuators):
        def callback():
            self.model.dm.actuators = new_actuators
            self.model.purge_plane('pre_turbulence')

        self.add_callback(at_time, callback)

    def update_atmosphere(self):
        self.log.info('Updating atmosphere.')

        t = self.time.get()[0]

        self.model.atmosphere.t = t
        self.model.purge_plane('pre_coro')

        self.add_callback(t + 0.01, self.update_atmosphere)

    def camera_readout(self, camera_name, power):
        image = power.shaped

        # Add semi-realistic noise for this camera.
        image = hcipy.large_poisson(image)
        image[image > 2**16] = 2**16
        image = image.astype('float32')

        # Put the image on the images datastream for this camera.
        try:
            camera = self.testbed.get_service(camera_name)

            if not camera.is_running:
                return

            if not np.allclose(camera.images.shape, image.shape):
                camera.images.update_parameters('float32', image.shape, 20)

            camera.images.submit_data(image)
        except Exception as e:
            self.log.error(str(e))

if __name__ == '__main__':
    service = SimpleSimulator()
    service.run()
