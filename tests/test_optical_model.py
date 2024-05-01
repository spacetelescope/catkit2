from catkit2.simulator import SimpleOpticalModel
import hcipy
import time
from catkit2.catkit_bindings import DataStream


model = SimpleOpticalModel()
pupil_grid = model.pupil_grid

wf_in = hcipy.Wavefront(pupil_grid.ones())
model.set_wavefronts('pre_pupil', wf_in)

test_wf = model.get_wavefronts('science_camera')[0]
size1 = test_wf.intensity.shaped.shape[0]
size2 = test_wf.intensity.shaped.shape[1]

stream = DataStream.create('images', 'mod', 'float64', [size1, size2], 20)
print(stream.stream_id)
time.sleep(1)

while True:
    model.atmosphere.t += 0.01
    model.purge_plane('pre_coro')

    wf_out = model.get_wavefronts('science_camera')[0]

    stream.submit_data(wf_out.intensity.shaped)
