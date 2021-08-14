from catkit2.core import *

ds = DataStream.open('abcd')

k = 0

while True:
    f = ds.get_next_frame()
    if k % 100 == 0:
        print(f.id, convert_timestamp_to_string(f.timestamp), f.data[0,0])

    k += 1
