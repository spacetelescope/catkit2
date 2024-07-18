from catkit2.simulator import OpticalModel, with_cached_result
import hcipy
import numpy as np


class ExampleOpticalModel(OpticalModel):
    """An example optical model for use with the example testbed.

    This class simulates a simple pupil mask and simple science camera. All parameters are read from
    the simulator configuration file, testbed_example/config/simulator.yml.
    """
    def __init__(self, config):
        super().__init__()

        self.config = config

        @self.register_plane('detector', 'pupil')
        def detector(wf):
            return self.prop(wf)

        @self.register_plane('pupil', 'light_source')
        def pupil(wf):
            return self.pupil_mask(wf)

    @property
    def pupil_grid(self):
        dimensions = self.config['pupil_mask']['dimensions']
        dims = np.array([dimensions, dimensions])
        size = self.config['pupil_mask']['grid_size']

        return hcipy.make_uniform_grid(dims, size)

    @property
    def detector_grid(self):
        roi = self.config['detector']['roi']
        dims = np.array([roi, roi])
        pixel_size = self.config['detector']['pixel_size']

        return hcipy.make_uniform_grid(dims, dims * pixel_size)

    @property
    @with_cached_result
    def prop(self):
        return hcipy.FraunhoferPropagator(self.pupil_grid, self.detector_grid)

    @property
    @with_cached_result
    def pupil_mask(self):
        diameter = self.config['pupil_mask']['diameter']
        mask = hcipy.circular_aperture(diameter)(self.pupil_grid)

        return hcipy.Apodizer(mask)
