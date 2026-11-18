from catkit2.simulator import OpticalModel, with_cached_result
import hcipy
import numpy as np


class {{cookiecutter.project_slug.capitalize()}}OpticalModel(OpticalModel):
    """An example optical model.
    This class simulates a simple pupil mask and simple science camera. All parameters are read from
    the model configuration file, {{cookiecutter.project_slug}}/config/model.yml.
    """
    def __init__(self, config, wavelength=700e-9):
        super().__init__()

        self.config = config
        self.wavelength = wavelength

        @self.register_plane('sample_camera', 'pupil')
        def sample_camera(wf):
            return self.prop(wf)

        @self.register_plane('pupil', 'light_source')
        def pupil(wf):
            return self.pupil_mask(wf)

        self.set_wavefronts('light_source', hcipy.Wavefront(self.pupil_grid.ones(), self.wavelength))

    @property
    def pupil_grid(self):
        dimensions = self.config['pupil_mask']['dimensions']
        dims = np.array([dimensions, dimensions])
        size = self.config['pupil_mask']['grid_size']

        return hcipy.make_uniform_grid(dims, size)

    @property
    def sample_camera_grid(self):
        roi = self.config['sample_camera']['roi']
        dims = np.array([roi, roi])
        pixel_size = self.config['sample_camera']['pixel_size']

        return hcipy.make_uniform_grid(dims, dims * pixel_size)

    @property
    @with_cached_result
    def prop(self):
        return hcipy.FraunhoferPropagator(self.pupil_grid, self.sample_camera_grid)

    @property
    @with_cached_result
    def pupil_mask(self):
        diameter = self.config['pupil_mask']['diameter']
        mask = hcipy.circular_aperture(diameter)(self.pupil_grid)

        return hcipy.Apodizer(mask)
