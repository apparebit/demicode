#!./venv/bin/python

"""
Repeatedly show terminal size. Most terminals don't show the fixed-width grid
size when resizing the window, which makes adjusting the window size
unnecessarily hard. This utility keeps printing the current terminal size into
the upper left corner of the terminal, thus helping hit the target size.
"""

from pathlib import Path
import sys

# Fix Python path to include project root
sys.path.insert(0, str(Path.cwd()))

from demicode.ui.termio import TermIO

if __name__ == "__main__":
    TermIO().resize_interactively(120, 40)
