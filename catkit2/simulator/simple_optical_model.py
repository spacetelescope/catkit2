from catkit2.simulator.optical_model import OpticalModel
import hcipy


class SimpleOpticalModel(OpticalModel):
    '''A simple optical model, showing the correct usage of an OpticalModel.

    This class simulates a simple pupil mask, perfect coronagraph, simple DM,
    simple atmosphere and simple science camera. All parameters are hard-coded
    for simplicity. This is not meant to be used directly, but serves as an
    example on how an OpticalModel derived class is supposed to work, without
    getting bogged down into the intricacies of a full model for an actual
    instrument.
    '''
    def __init__(self):
        super().__init__()

        @self.register_plane('science_camera', 'post_coro')
        def science_camera(wf):
            return self.prop(wf)

        @self.register_plane('post_coro', 'pre_coro')
        def coro(wf):
            return self.coro(wf)

        @self.register_plane('pre_coro', 'pre_turbulence')
        def turbulence(wf):
            return self.atmosphere(wf)

        @self.register_plane('pre_turbulence', 'pre_dm')
        def dm(wf):
            return self.dm(wf)

        @self.register_plane('pre_dm', 'pre_pupil')
        def pupil(wf):
            return self.pupil_mask(wf)

    @property
    def pupil_grid(self):
        return hcipy.make_pupil_grid(578)

    @property
    def focal_grid(self):
        return hcipy.make_focal_grid(12, 32)

    @property
    @with_cached_result
    def prop(self):
        return hcipy.FraunhoferPropagator(self.pupil_grid, self.focal_grid)

    @property
    @with_cached_result
    def atmosphere(self):
        r0 = 30
        outer_scale = 20
        velocity = 0.3

        Cn_squared = hcipy.Cn_squared_from_fried_parameter(r0, 1)
        return hcipy.InfiniteAtmosphericLayer(self.pupil_grid, Cn_squared, outer_scale, velocity)

    @property
    @with_cached_result
    def coro(self):
        return hcipy.PerfectCoronagraph(hcipy.make_hicat_aperture(True)(self.pupil_grid))

    @property
    @with_cached_result
    def dm(self):
        influence_functions = hcipy.make_xinetics_influence_functions(self.pupil_grid, 11, 1 / 11)

        return hcipy.DeformableMirror(influence_functions)

    @property
    @with_cached_result
    def pupil_mask(self):
        mask = hcipy.make_hicat_aperture(True)(self.pupil_grid)
        return hcipy.Apodizer(mask)
