import numpy as np
import matplotlib.pyplot as plt
import time

from hicat2.protocol.client import *

testbed = TestbedClient(8080)

t1 = testbed.tsp01_1
t2 = testbed.tsp01_2
t3 = testbed.tsp01_3

times = []
temperatures = []

while True:
    ts = []

    ts.append(t1.temperature_internal.get()[0])
    ts.append(t1.temperature_header_1.get()[0])
    ts.append(t1.temperature_header_2.get()[0])

    ts.append(t2.temperature_internal.get()[0])
    ts.append(t2.temperature_header_1.get()[0])
    ts.append(t2.temperature_header_2.get()[0])

    ts.append(t3.temperature_internal.get()[0])
    ts.append(t3.temperature_header_1.get()[0])
    ts.append(t3.temperature_header_2.get()[0])

    times.append(np.datetime64('now'))
    temperatures.append(ts)

    plt.clf()
    plt.plot(times, temperatures)
    plt.draw()
    plt.pause(10)
