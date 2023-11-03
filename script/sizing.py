#!./venv/bin/python

"""
Repeatedly show terminal size. Most terminals don't show the fixed-width grid
size when resizing the window, which makes adjusting the window size
unnecessarily hard. This utility keeps printing the current terminal size into
the upper left corner of the terminal, thus helping hit the target size.
"""

import os
import time

SLEEP = 2/3

if __name__ == '__main__':
    try:
        # 47/1047 won't do since they don't save cursor state.
        print('\x1b[?1049h', end=None)  # Use alternate buffer
        print('\x1b[?25l', end=None)  # Hide cursor

        block = False
        while True:
            # Update state
            width, height = os.get_terminal_size()
            block = not block
            char = '█' if block else ' '

            # Display state
            print(
                f'\x1b[H\x1b[2J{width:3d} x {height:3d} {char}',
                end=None
            )

            # Take nap
            time.sleep(SLEEP)
    except KeyboardInterrupt:
        pass
    finally:
        print('\x1b[?25h', end=None)  # Show cursor
        print('\x1b[?1049l', end=None)  # Use regular buffer
