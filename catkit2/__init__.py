# flake8: noqa

# Setting to ensure CTRL-C commands are caught, which allows services to exit properly.
import os
os.environ['FOR_DISABLE_CONSOLE_CTRL_HANDLER'] = '1'

# Enable printing of stacktrace upon segfault.
import faulthandler
faulthandler.enable()

from . import testbed
from . import simulator
from . import config

from .testbed import *
from .simulator import *
from .config import *

from .version import get_version
__version__ = get_version()

__all__ = []
__all__.extend(testbed.__all__)
__all__.extend(simulator.__all__)
