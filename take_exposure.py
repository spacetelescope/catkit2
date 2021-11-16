from hicat2.testbed import Testbed
from hicat2.interfaces import *

import numpy as np
import matplotlib.pyplot as plt

print('start')
testbed = Testbed(8080)                                 # Establish connection to the testbed server.

cam = testbed.example_camera                            # Start up / connect to the camera.
imgs = list(cam.take_exposures(num_exposures=10))       # Take exposures and put them in a list.

print('end')

img = np.mean(imgs, axis=0)

plt.imshow(img, cmap='inferno')
plt.colorbar()
plt.show()
