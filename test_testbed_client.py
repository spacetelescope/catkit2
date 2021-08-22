from hicat2.testbed import *
from hicat2.bindings import convert_timestamp_to_string
import time

testbed = Testbed(8080)
a = testbed.a

for i in range(20):
    f = a.temperature.get_next_frame()
    print(f.id, convert_timestamp_to_string(f.timestamp), f.data)

# FIXED: name in DataStream
# FIXED: num dimensions for 1 element data in datastream
# FIXED: error checking HANDLES for shmem
# FIXED: shut down zmq sockets when main module function ends

# search locations for module types
# register new module names
# helper/convenience functions (take_exposures, apply_shape, flip_in_beam, etc...)
# logging broadcasting for modules
