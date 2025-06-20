#!./venv/bin/python

import argparse
import os
import sys

sys.path.insert(0, '')

from demicode.ui.terminal import Terminal


CSI = '\x1b['
FAINT = f'{CSI}38;5;248m'
LEGEND = f'{CSI}3;38;5;240m'
ORANGE = f'{CSI}38;5;202m'
YELLOW = f'{CSI}38;5;220m'
BLUE = f'{CSI}38;5;63m'
RESET = f'{CSI}0m'
INDENT = '        '
PREFIX = '\u2E3B\u2A0C{sep}\U0001F9D1\u200D\U0001F4BB'
MARKERS1 = '▽▽▽▽▼▽▽▽▽▼'
MARKERS2 = '△△△△▲△△△△▲'
MARKERS3 = '    5    1    1    2    2    3    3    4    4    5'
MARKERS4 = '         0    5    0    5    0    5    0    5    0'


def mkbar() -> str:
    width, _ = os.get_terminal_size()
    return '\x1b[48;5;196m' + (' ' * width) + '\x1b[0m'


def mklabels(tens: int) -> tuple[str, str]:
    terminal = Terminal.current()
    if terminal.version is None:
        return terminal.long_name, ''
    display = terminal.display
    if len(display) <= tens * 10:
        return display, ''
    else:
        return terminal.long_name, terminal.version


def mkprefix(spaces: int) -> str:
    return f'\u2E3B\u2A0C{" " * spaces}\U0001F9D1\u200D\U0001F4BB'


def print_payload(bar1: str, label1: str, label2: str, payload: str, bar2: str, tens: int) -> None:
    print('\n')
    print(bar1)
    print('\n')

    width = 10 * tens
    print(f'{INDENT}{LEGEND}{label1.center(width)}{RESET}')
    if label2 != '':
        print(f'{INDENT}{LEGEND}{label2.center(width)}{RESET}')
    print(f'{INDENT}{FAINT}{MARKERS1 * tens}{RESET}')
    print(f'{INDENT}{payload}')
    print(f'{INDENT}{FAINT}{MARKERS2 * tens}{RESET}')
    print(f'{INDENT}{FAINT}{MARKERS3[0: width]}{RESET}')
    print(f'{INDENT}{FAINT}{MARKERS4[0: width]}{RESET}')
    print('\n')
    if bar2:
        print(bar2)
        print('\n')

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'payload',
        choices=['dash-integral', 'spaced-dash-integral', 'arab-ligature', 'hello'],
    )
    options = parser.parse_args()

    bar = mkbar()

    payload2 = None
    if options.payload == 'arab-ligature':
        payload1 = '\uFDFD'
        tens = 2
    elif options.payload == 'spaced-dash-integral':
        payload1 = f' {FAINT}█{RESET} '.join(mkprefix(w) for w in range(3))
        tens = 3
    elif options.payload == 'dash-integral':
        payload1 = mkprefix(0) + '\uFF0A𝔽𝕚𝕩𝕖𝕕-𝐖𝐢𝐝𝐭𝐡'
        payload2 = mkprefix(3) + f'{FAINT}█{RESET}\uFF0A{FAINT}█{RESET}𝔽𝕚𝕩𝕖𝕕-𝐖𝐢𝐝𝐭𝐡'
        tens = 3
    elif options.payload == 'hello':
        payload1 = 'Hello  سلام  नमस्ते  שלום'
        payload2 = 'こんにちは  Привет  你好'
        tens = 3
    else:
        raise ValueError(f'invalid payload "{options.payload}"')

    label1, label2 = mklabels(tens)
    print_payload(bar, label1, label2, payload1, '' if payload2 else bar, tens)
    if payload2:
        print_payload(bar, label1, label2, payload2, bar, tens)

if __name__ == '__main__':
    main()
