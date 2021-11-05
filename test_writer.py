from hicat2.bindings import *
import time
import numpy as np

ds = DataStream.create('abcd', 'module', 'H', [512,512], 20)
print('Waiting...')
time.sleep(10)

n = 30

for i in range(100000):
    f = ds.request_new_frame()
    f.data[:n] = (np.random.uniform(0, 1000, size=n*512).reshape((n,512))).astype('uint16')
    #if f.id % 10000 == 0:
    #    print(f.id)
    #    print(f.data)

    ds.submit_frame(f.id)
