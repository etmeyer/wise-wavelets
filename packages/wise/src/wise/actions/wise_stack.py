#! /usr/bin/env python
# CLI entry point migrated to wise.cli (click). This module is kept for importability.

import wise
from . import actions

USAGE = '''Stack images

Usage: wise stack FILES_OR_FILE_LIST [-o OUTPUT_FITS]

Additional options:
--output FILENAME, -o FILENAME: output file name (default=stack_img.fits)
--nsigma NSIGMA, -n NSIGMA: clip background below NSIGMA level (default=0)
--nsigma_connected, -c: Keep only the brightest isolated structure
'''
