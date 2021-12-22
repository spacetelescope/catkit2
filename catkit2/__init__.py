from . import testbed
from . import simulator
from . import config

from .testbed import *
from .simulator import *
from .config import *

__all__ = []
__all__.extend(testbed.__all__)
__all__.extend(simulator.__all__)

from .version import get_version
__version__ = get_version()

# Setting to ensure CTRL-C commands are caught, which allows services to exit properly.
import os
os.environ['FOR_DISABLE_CONSOLE_CTRL_HANDLER'] = '1'
