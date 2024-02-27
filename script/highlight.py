#!./venv/bin/python

import argparse
import io
import os
import sys
from typing import TextIO

sys.path.insert(0, '')

from demicode.ui.terminal import Terminal


INDENT = '    '

def highlight(input: TextIO, output: TextIO) -> None:
    terminal = Terminal.current()

    try:
        width, _ = os.get_terminal_size(output.fileno())
    except:
        width = 80

    output.write('\x1b[48;5;196m' + (' ' * width) + '\x1b[0m\n\n')
    output.write(f'{INDENT}\x1b[1;3m{terminal.display}:\x1b[22;23m\n')

    is_first_line = True
    last_line_was_empty = False

    for line in input:
        is_empty = (line == '\n')
        if is_first_line:
            is_first_line = False
            if not is_empty:
                output.write('\n')
        else:
            last_line_was_empty = is_empty

        output.write(INDENT + line)

    if not last_line_was_empty:
        output.write('\n')

    output.write('\x1b[48;5;196m' + (' ' * width) + '\x1b[0m\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        'file',
        default=None,
        nargs='?',
        metavar='FILE',
        help='highlight contents of text file instead of this help text',
    )
    options = parser.parse_args()
    if options.file:
        with open(options.file, mode='r', encoding='utf8') as input:
            highlight(input, sys.stdout)
    else:
        highlight(io.StringIO(parser.format_help()), sys.stdout)
