from catkit2.catkit_bindings import DataStream
import numpy as np
import time

mask = np.random.randn(2048) > 0
mat = np.random.randn(128, int(np.sum(mask)))

stream = DataStream.open('20212.boston_dm.correction_howfs')
print('opened')
while True:
    a = stream.get()
    b = a[mask]

    np.dot(mat, b)
