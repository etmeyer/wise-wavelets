#! /usr/bin/env python
# CLI entry point migrated to wise.cli (click). This module is kept for
# importability.

import wise
from . import actions

USAGE = '''Plot all features on a distance from core vs epoch

Usage: wise plot_features NAME SCALES

NAME: the name of the saved result set to use.
SCALES: coma separated list of scales to plot.

Additional options:
--pa, -p: Additionally plot the features positional angle vs epoch
'''
