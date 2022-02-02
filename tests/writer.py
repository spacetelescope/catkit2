from catkit2.catkit_bindings import DataStream
import time
import numpy as np

stream = DataStream.create('correction_howfs', 'boston_dm', 'float64', [2048], 20)
stream.submit_data(np.zeros(2048))

print(stream.stream_id)
time.sleep(100000)
