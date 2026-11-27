#!/usr/bin/env python3
"""KiCad Library Manager - PySide6 GUI for managing KiCad library tables.

Usage: python kicad_lib_manager.py [--library-root PATH] [--scratch-root PATH]
(or set KICAD_LIBMGR_ROOT to the library folder and KICAD_LIBMGR_SCRATCH_ROOT to a scratch folder;
the command line wins). With a scratch folder the app's settings, saved scans, backups and KiCad's
settings are read and written under it, never in your real folders: for rehearsals and owner checks.
"""

import sys

from kicad_lib_manager.startup import run


def main():
    sys.exit(run(sys.argv))


if __name__ == "__main__":
    main()
