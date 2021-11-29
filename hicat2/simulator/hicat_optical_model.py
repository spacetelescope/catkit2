from .optical_model import *

class HicatOpticalModel(OpticalModel):
    def __init__(self, with_aberrations=True):
        super().__init__()

        self.setup_propagators()

        @self.register_plane('science_camera', 'post_ncpa')
        def science_camera(wf_post_ncpa):
            return self.prop_science_camera(self.nd_flip_mount(wf_post_ncpa))

        @self.register_plane('pupil_camera', 'post_ncpa')
        def pupil_camera(wf_post_ncpa):
            return self.reimager_pupil_camera(wf_post_ncpa)

        @self.register_plane('post_ncpa', 'pre_ncpa')
        def post_ncpa(wf_pre_ncpa):
            return self.ncpa(wf_pre_ncpa)

        @self.register_plane('pre_ncpa', 'pre_lyot_stop')
        def pre_ncpa(wf_pre_lyot_stop):
            return self.lyot_stop(wf_pre_lyot_stop)

        @self.register_plane('zernike_camera', 'lowfs_pupil')
        def zernike_camera(wf_lowfs_pupil):
            return self.reimager_zernike_camera(self.zernike_mask(wf_lowfs_pupil))

        @self.register_plane('ta_camera', 'lowfs_pupil')
        def ta_camera(wf_lowfs_pupil):
            return self.prop_ta_camera(wf_lowfs_pupil)

        @self.register_plane('lopr_camera', 'lowfs_pupil')
        def lopr_camera(wf_lowfs_pupil):
            return self.prop_lopr_camera(self.lopr_camera_defocus(wf_lowfs_pupil))

        @self.register_plane('pre_lyot_stop', 'post_common_aberrations')
        def pre_lyot_stop(wf_post_common_aberrations):
            return self.magnifier_dm_to_lyot_stop(self.coro(wf_post_common_aberrations))

        @self.register_plane('lowfs_pupil', 'post_common_aberrations')
        def lowfs_pupil(wf_post_common_aberrations):
            return self.fpm_to_lowfs(self.fpm(self.dm_to_fpm(wf_post_common_aberrations)))

        @self.register_plane('pr_camera', 'post_common_aberrations')
        def pr_camera(wf_post_common_aberrations):
            return self.prop_pr_camera(self.defocus_pr_camera(wf_post_common_aberrations))

        @self.register_plane('post_common_aberrations', 'pre_common_aberrations')
        def post_common_aberrations(wf_pre_common_aberrations):
            return self.beam_dump(self.common_aberrations(wf_pre_common_aberrations))

        @self.register_plane('pre_common_aberrations', 'pre_boston_dms')
        def pre_common_aberrations(wf_pre_boston_dms):
            return self.fresnel.backward(self.dm2(self.fresnel.forward(self.dm1(wf_pre_boston_dms))))

        @self.register_plane('pre_boston_dms', 'pre_apodizer')
        def pre_boston_dms(wf_pre_apodizer):
            return self.magnifier_apodizer_to_dm(self.apodizer(wf_pre_apodizer))

        @self.register_plane('pre_apodizer', 'pre_iris_dm')
        def pre_apodizer(wf_pre_iris_dm):
            return self.magnifier_iris_to_apodizer(self.iris_dm(wf_pre_iris_dm))

        @self.register_plane('pre_iris_dm', 'pre_pupil_mask')
        def pre_iris_dm(wf_pre_pupil_mask):
            return self.magnifier_pupil_to_iris(self.pupil_mask(wf_pre_pupil_mask))

    def setup_propagators(self):
        self.create_apodizer()
        self.create_tip_tilt_mirror()

        self.create_pupil_mask()
        self.create_irisao_dm()
        self.create_boston_dms()

        self.create_beam_dump()
        self.create_nd_filter()
        self.create_nd_flip_mount()
        self.create_wavefront_error()

        self.create_focal_plane_mask()
        self.create_lyot_stop()

        self.create_phase_retrieval_camera()
        self.create_zernike_camera()
        self.create_science_camera()
        self.create_pupil_camera()
        self.create_target_acquisition_camera()
        self.create_lopr_camera()

    @property
    def apodizer_mask_name(self):
        return self._apodizer_mask_name

    @apodizer_mask_name.setter
    def apodizer_mask_name(self, apodizer_mask_name):
        self._apodizer_mask_name = apodizer_mask_name

        self.apodizer_mask = read_field(self.apodizer_mask_name)
        self._apodizer = None

    @property
    @with_cached_result
    def apodizer(self):
        return Apodizer(self.apodizer_mask)

    @property
    @with_cached_result
    def tip_tilt_mirror(self):


    def create_pupil_mask(self):
        pass

    def create_irisao_dm(self):
        pass

    def create_boston_dms(self):
        pass

    def create_beam_dump(self):
        pass

    def create_nd_filter(self):
        pass

    def create_nd_flip_mount(self):
        pass

    def create_wavefront_error(self):
        pass

    def create_focal_plane_mask(self):
        pass

    def create_lyot_stop(self):
        pass

    def create_phase_retrieval_camera(self):
        pass

    def create_zernike_camera(self):
        pass

    def create_science_camera(self):
        pass

    def create_pupil_camera(self):
        pass

    def create_target_acquisition_camera(self):
        pass

    def create_lopr_camera(self):
        pass

    @property
    def apodizer_shift_x(self):
        return self._apodizer_shift_x

    @apodizer_shift_x.setter
    def apodizer_shift_x(self, shift_x):
        self._apodizer_shift_x = shift_x
        self.create_apodizer()
