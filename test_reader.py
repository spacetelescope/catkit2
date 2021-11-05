from hicat2.bindings import *

ds = DataStream.open('abcd', 'module')
ds.buffer_handling_mode = BufferHandlingMode.OLDEST_FIRST_OVERWRITE
#ds.buffer_handling_mode = BufferHandlingMode.NEWEST_ONLY

k = 0

try:
    while True:
        f = ds.get_next_frame()
        if k % 1000 == 0:
            print(f.id, k, f.timestamp)
            #print(f.id, convert_timestamp_to_string(f.timestamp), f.data[0,0])

        k += 1
except KeyboardInterrupt:
    print(f.id, k)
