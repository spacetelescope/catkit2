from hicat2.simulator.simple_optical_model import SimpleOpticalModel
import hcipy
import time
from catkit2.bindings import DataStream


model = SimpleOpticalModel()
pupil_grid = model.pupil_grid

wf_in = hcipy.Wavefront(pupil_grid.ones())
model.set_wavefronts('pre_pupil', wf_in)

stream = DataStream.create('images', 'mod', 'float64', [12*16, 12*16], 20)
print(stream.stream_id)
time.sleep(1)

while True:
    model.atmosphere.t += 0.01
    model.purge_plane('pre_coro')

    wf_out = model.get_wavefronts('science_camera')[0]

    stream.submit_data(wf_out.intensity.shaped)
