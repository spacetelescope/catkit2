from hicat2.bindings import *
import time
import numpy as np

N = 128

ds = DataStream.create('abcd', 'module', 'H', [N,N], 20)
print(ds.stream_id)
print('Waiting...')
time.sleep(10)

n = 30

for i in range(100000):
    data = np.random.uniform(0, 1000, size=N*N).reshape((N,N)).astype('uint16')
    ds.submit_data(data)
    #f = ds.request_new_frame()
    #f.data[:] = data
    #ds.submit_frame(f.id)

    #if f.id % 10000 == 0:
    #    print(f.id)
    #    print(f.data)

    if i % 10 == 0:
        print(i)
