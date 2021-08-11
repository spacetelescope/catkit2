from catkit2.data_streams import *

ds = DataStream.open('abcd')

while True:
    f = ds.get_next_frame()
    if f.id % 1000 == 0:
        print(f.id, convert_timestamp_to_string(f.timestamp), f.data.shape)
