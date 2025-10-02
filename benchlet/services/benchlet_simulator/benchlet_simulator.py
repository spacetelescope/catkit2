from catkit2.simulator import Simulator
from benchlet.benchlet_optical_model import BenchletOpticalModel
import hcipy


class BenchletSimulator(Simulator):
    """A very simple example simulator for the example testbed "Benchlet".

    This service provides the simulator interface to the connected optical model.
    """
    def __init__(self):
        super().__init__('benchlet_simulator')
        self.light_source_data = {}
        
    def open(self):
        self.model = BenchletOpticalModel(self.testbed.config['simulator'])
        wavefronts = [hcipy.Wavefront(self.model.pupil_grid.ones() * 1e5)]
        self.model.set_wavefronts('light_source', wavefronts)
        self.images = self.make_data_stream('images', 'float64', self.model.detector_grid.shape, 20)

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
    service = BenchletSimulator()
    service.run()
