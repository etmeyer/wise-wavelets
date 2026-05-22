#! /usr/bin/env python
# CLI entry point migrated to wise.cli (click). This module is kept for
# importability.

import wise
from . import actions

USAGE = '''Set and get WISE configuration.

Possible actions are:

wise settings set SECTION.OPTION=VALUE [SECTION.OPTION=VALUE]
wise settings get/show [SECTION[.OPTION]]
wise settings doc [SECTION[.OPTION]]
wise settings restore CONFIG_FILE

SECTION is one of data, finder or matcher
'''
