#!/usr/bin/env python3
"""KiCad Library Manager - PySide6 GUI for managing KiCad library tables.

Usage: python kicad_lib_manager.py [--library-root PATH]
(or set KICAD_LIBMGR_ROOT to the library folder).
"""

import sys

from kicad_lib_manager.startup import run


def main():
    sys.exit(run(sys.argv))


if __name__ == "__main__":
    main()
