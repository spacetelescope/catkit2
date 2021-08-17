from hicat_hardware import *
import time
import numpy as np

ds = DataStream.create('abcd', 'H', [512,512], 20)
print('Waiting...')
time.sleep(10)

for i in range(100000):
    f = ds.request_new_frame()
    f.data[:50] = (np.random.uniform(0, 1000, size=50*512).reshape((50,512))).astype('uint16')
    if f.id % 10000 == 0:
        print(f.id)
        print(f.data)

    ds.submit_frame(f.id)
