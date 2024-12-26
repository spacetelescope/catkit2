import matplotlib.pyplot as plt
import numpy as np

latencies = []

with open('results.txt') as f:
    for line in f.readlines():
        latencies.append(float(line) / 1000)

print(len(latencies))

plt.hist(latencies, bins=np.arange(0, 100))
plt.yscale('log')

quantiles = [0.5, 0.99, 0.999, 0.9999]
for q in quantiles:
    p = np.quantile(latencies, q)
    plt.axvline(p, c='k')
    plt.text(p, 1e6, f'{float(q * 100)}%', horizontalalignment='right', verticalalignment='bottom', rotation=90)
plt.ylim(5e-1, 2e7)

plt.xlabel('Latency [us]')
plt.ylabel('Occurance')
plt.show()
