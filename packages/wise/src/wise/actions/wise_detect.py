#! /usr/bin/env python
# CLI entry point migrated to wise.cli (click). This module is kept for importability.

import wise
from . import actions

USAGE = '''Run the Segmented wavelet decomposition

Usage: wise detect FILES_OR_FILE_LIST

Arguments can be either the files to process, or a text file listing the files
to process.
'''
