#! /usr/bin/env python
# CLI entry point migrated to wise.cli (click). This module is kept for
# importability.

import wise
from . import actions

USAGE = '''Plot all features location on the reference image.

Usage: wise view_features NAME SCALES

NAME: the name of the saved result set to use.
SCALES: coma separated list of scales to plot.
'''
