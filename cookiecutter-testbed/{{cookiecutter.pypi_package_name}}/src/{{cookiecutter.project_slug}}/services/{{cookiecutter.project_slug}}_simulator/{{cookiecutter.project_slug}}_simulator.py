from catkit2.simulator import Simulator
from {{cookiecutter.project_slug}}.{{cookiecutter.project_slug}}_optical_model import {{cookiecutter.project_slug.capitalize()}}OpticalModel
import hcipy


class {{cookiecutter.project_slug.capitalize()}}Simulator(Simulator):
    """A very simple example simulator for the example testbed "{{cookiecutter.project_slug.capitalize()}}".
    This service provides the simulator interface to the connected optical model.
    """
    def __init__(self):
        super().__init__('{{cookiecutter.project_slug}}_simulator')
        self.light_source_data = {}

    def open(self):
        self.model = {{cookiecutter.project_slug.capitalize()}}OpticalModel(self.testbed.config['simulator'])
        wvln = 1
        wavefronts = [hcipy.Wavefront(self.model.pupil_grid.ones() * 1e5, wvln)]
        self.model.set_wavefronts('light_source', wavefronts)
        self.images = self.make_data_stream('images', 'float64', self.model.sample_camera_grid.shape, 20)

    def camera_readout(self, camera_name, power):
        image = power.shaped
        image = hcipy.large_poisson(image)
        image[image > 2**16] = 2**16
        image = image.astype('float32')

        try:
            self.testbed.sample_camera.images.update_parameters('float32', image.shape, 20)
            self.testbed.sample_camera.images.submit_data(image)
        except Exception as e:
            self.log.error(str(e))

    def get_camera_power(self, camera_name):
        wavefronts = self.model.get_wavefronts(camera_name)
        return sum(wf.power for wf in wavefronts)


if __name__ == '__main__':
    service = {{cookiecutter.project_slug.capitalize()}}Simulator()
    service.run()
