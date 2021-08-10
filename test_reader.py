from catkit2.data_streams import *

ds = DataStream.open('abcd')

while True:
    f = ds.get_next_frame()
    if f.id % 1000 == 0:
        print(f.id)
        print('data', f.data[0,0], f.data.shape)
