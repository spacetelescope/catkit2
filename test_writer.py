from catkit2.data_streams import *
import time

ds = DataStream.create('abcd', 'H', [512,512], 20)
print('Waiting...')
time.sleep(10)

for i in range(100000):
    f = ds.request_new_frame()
    if f.id % 1000 == 0:
        print(f.id)
        print(f.data)
    f.data[:] = i

    ds.submit_frame(f.id)
