from catkit2.catkit_bindings import DataStream
from catkit2.simulator import SimpleOpticalModel

import hcipy
import numpy as np


def test_optical_model():
    model = SimpleOpticalModel()
    pupil_grid = model.pupil_grid

    wf_in = hcipy.Wavefront(pupil_grid.ones())
    model.set_wavefronts('pre_pupil', wf_in)

    for i in range(5):
        model.atmosphere.t += 0.01
        model.purge_plane('pre_coro')

        wf_out = model.get_wavefronts('science_camera')[0]

        assert np.sum(wf_out.intensity) > 0
