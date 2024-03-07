__all__ = []

[
    'CameraProxy',
    'NewportXpsQ8Proxy',
    'FlipMountProxy',
    'BmcDmProxy',
    'NewportPicomotorProxy',
    'NiDaqProxy',
    'NktSuperkProxy',
    'WebPowerSwitchProxy'
]

try:
    from .bmc_dm import *
    __all__.append('BmcDmProxy')
except ImportError:
    print('BmcDmProxy not imported')

try:
    from .camera import *
    __all__.append('CameraProxy')
except ImportError:
    print('CameraProxy not imported')

try:
    from .newport_xps import *
    __all__.append('NewportXpsQ8Proxy')
except ImportError:
    print('NewportXpsQ8Proxy not imported')


try:
    from .flip_mount import *
    __all__.append('FlipMountProxy')
except ImportError:
    print('FlipMountProxy not imported')

try:
    from .newport_picomotor import *
    __all__.append('NewportPicomotorProxy')
except ImportError:
    print('NewportPicomotorProxy not imported')

try:
    from .ni_daq import *
    __all__.append('NiDaqProxy')
except ImportError:
    print('NiDaqProxy not imported')

try:
    from .nkt_superk import *
    __all__.append('NktSuperkProxy')
except ImportError:
    print('NktSuperkProxy not imported')

try:
    from .web_power_switch import *
    __all__.append('WebPowerSwitchProxy')
except ImportError:
    print('WebPowerSwitchProxy not imported')
