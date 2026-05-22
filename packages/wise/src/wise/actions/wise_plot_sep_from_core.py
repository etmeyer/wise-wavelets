#! /usr/bin/env python
# CLI entry point migrated to wise.cli (click). This module is kept for
# importability.

import wise
from . import actions

USAGE = '''Plot separation from core with time

Usage: wise plot_sep_from_core NAME SCALES

NAME: the name of the saved result set to use.
SCALES: coma separated list of scales to plot.

Additional options:
--pa, -p: Additionally plot the features positional angle vs epoch
--fit, -f: fit each links with a linear fct
--num, -n: Annotate each links
--min-link-size=INT, -m INT: Filter out links with size < min_link_size (default=2)
'''
