#! /usr/bin/env python
# CLI entry point migrated to wise.cli (click). This module is kept for
# importability.

import wise
from . import actions

USAGE = '''Plot all components trajectories on the reference map

Usage: wise view_links NAME SCALES

NAME: the name of the saved result set to use.
SCALES: coma separated list of scales to plot.

Additional options:
--min-link-size=INT, -m INT: Filter out links with size < min_link_size (default=2)
'''
