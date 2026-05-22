#! /usr/bin/env python
# CLI entry point migrated to wise.cli (click). This module is kept for
# importability; the wise_info.main() shim below is dead code.

import wise
from . import actions

USAGE = '''Give information on beam, pixel scales or velocity resolution

Usage: wise info FILES_OR_FILE_LIST

Additional options:
--velocity, -V: gives information on velocity resolution
'''
