#! /usr/bin/env python
# CLI entry point migrated to wise.cli (click). This module is kept for
# importability.

import wise

USAGE = '''Build a list of files and output the listing in OUTPUT_FILE.

Usage: wise select_files FILES [-o OUTPUT_FILE]

Additional options:
--output FILENAME, -o FILENAME: output file name (default=files)
--start-date=START, -s START: filter files with date < START
--end-date=END -e END: filter files with date > END
--filter-date=DATE, -f DATE: filter files with date == DATE

All dates must be formated as: YYYY-MM-DD
'''
