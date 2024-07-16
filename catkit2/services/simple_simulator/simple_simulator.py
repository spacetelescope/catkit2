from catkit2.simulator import SimpleOpticalModel, Simulator
import hcipy


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

        self.images = self.make_data_stream('images', 'float64', self.model.focal_grid.shape, 20)

        self.update_atmosphere

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

        self.add_callback(self.update_atmosphere, t + 0.01)

    def camera_readout(self, camera_name, power):
        image = power.shaped
        image = hcipy.large_poisson(image)
        image[image > 2**16] = 2**16
        image = image.astype('float32')

        try:
            self.testbed.science_camera.images.update_parameters('float32', image.shape, 20)
            self.testbed.science_camera.images.submit_data(image)
        except Exception as e:
            self.log.error(str(e))

    def get_camera_power(self, camera_name):
        wavefronts = self.model.get_wavefronts(camera_name)
        return sum(wf.power for wf in wavefronts)

if __name__ == '__main__':
    service = SimpleSimulator()
    service.run()
