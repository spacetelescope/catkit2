from catkit2.catkit_bindings import DataStream
import time
import numpy as np

stream = DataStream.create('correction_howfs', 'boston_dm', 'float64', [2048], 20)
stream.submit_data(np.zeros(2048))

print(stream.stream_id)
time.sleep(10)
for i in range(1000):
    #time.sleep(1)
    np.random.randn(10000)
    print(stream.newest_available_frame_id)
    stream.submit_data(np.random.randn(2048))

