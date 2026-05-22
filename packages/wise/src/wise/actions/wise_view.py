#! /usr/bin/env python
# CLI entry point migrated to wise.cli (click). This module is kept for
# importability.

import wise
from . import actions

USAGE = '''Simple image viewer

Usage: wise view FILES

Additional options:
--no-crop, -n: do not crop images according to the data.roi_coords configuration
--no-align: do not align images according to the data.core_offset_filename file
--show-mask, -m: overplot the images with the mask, if it exist
--reg-file=FILE: -r FILE: overplot region, multiple option possible
'''
