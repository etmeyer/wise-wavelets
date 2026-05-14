import os

# Pin matplotlib's Qt binding before any matplotlib/Qt import below pulls
# qt_compat in and picks one. setdefault preserves an explicit user override.
os.environ.setdefault("QT_API", "pyqt5")

import libwise

# We need some extra bits to handle numpy array pickling correctly
from . import jsonpickle_numpy, tasks
from .features import *
from .matcher import *
from .project import *
from .scc import *
from .wds import *
from .wiseutils import *

__version__ = '0.5.0.dev1'


def get_version():
    return '%s (libwise: %s)' % (__version__, libwise.get_version())


jsonpickle_numpy.register_handlers()
