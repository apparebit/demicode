#!.venv/bin/python

"""
Repeatedly show terminal size. Most terminals don't show the fixed-width grid
size when resizing the window, which makes adjusting the window size
unnecessarily hard. This utility keeps printing the current terminal size into
the upper left corner of the terminal, thus helping hit the target size.
"""

import os
import time

SLEEP = 0.5

if __name__ == '__main__':
    try:
        block = False
        print('\x1b[?25l')  # Hide cursor

        while True:
            # Update the width and height
            width, height = os.get_terminal_size()
            print(f'\x1b[H\x1b[2J{width:3d} x {height:3d}')

            # Update liveness indicator
            block = not block
            char = '█' if block else ' '
            print(f'\x1b[2;1H{char}')

            # Take a nap
            time.sleep(SLEEP)
    except KeyboardInterrupt:
        pass
    finally:
        print('\x1b[?25h')  # Show cursor
