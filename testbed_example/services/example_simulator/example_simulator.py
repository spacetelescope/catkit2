from catkit2.simulator import Simulator
from testbed_example.example_optical_model import ExampleOpticalModel
import hcipy


class ExampleSimulator(Simulator):
    """A very simple example simulator for the example testbed.

    This service provides the simulator interface to the connected optical model.
    """
    def __init__(self):
        super().__init__('example_simulator')

    def open(self):
        self.model = ExampleOpticalModel()
        wavefronts = [hcipy.Wavefront(self.model.pupil_grid.ones() * 1e6)]
        self.model.set_wavefronts('pre_pupil', wavefronts)

        self.images = self.make_data_stream('images', 'float64', self.model.focal_grid.shape, 20)

    def camera_readout(self, camera_name, power):
        image = power.shaped
        image = hcipy.large_poisson(image)
        image[image > 2**16] = 2**16
        image = image.astype('float32')

        try:
            self.testbed.detector.images.update_parameters('float32', image.shape, 20)
            self.testbed.detector.images.submit_data(image)
        except Exception as e:
            self.log.error(str(e))

    def get_camera_power(self, camera_name):
        wavefronts = self.model.get_wavefronts(camera_name)
        return sum(wf.power for wf in wavefronts)


if __name__ == '__main__':
    service = ExampleSimulator()
    service.run()
