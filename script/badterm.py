#!./venv/bin/python

import argparse
import os
import sys

sys.path.insert(0, '')

from demicode.ui.terminal import determine_terminal_and_version


CSI = '\x1b['
FAINT = f'{CSI}38;5;248m'
LEGEND = f'{CSI}3;38;5;240m'
ORANGE = f'{CSI}38;5;202m'
YELLOW = f'{CSI}38;5;220m'
BLUE = f'{CSI}38;5;63m'
RESET = f'{CSI}0m'
INDENT = '        '
PREFIX = '\u2E3B\u2A0C{sep}\U0001F9D1\u200D\U0001F4BB'
WIDTH = 29


def mkbar() -> str:
    width, _ = os.get_terminal_size()
    return '\x1b[48;5;196m' + (' ' * width) + '\x1b[0m'


def mklabels() -> tuple[str, str]:
    terminal, version = determine_terminal_and_version()
    if terminal is None:
        return 'Unknown Terminal', ''
    elif version is None:
        return terminal, ''
    elif len((combined := f'{terminal} ({version})')) <= WIDTH:
        return combined, ''
    else:
        return terminal, version


def mkprefix(spaces: int) -> str:
    return f'\u2E3B\u2A0C{" " * spaces}\U0001F9D1\u200D\U0001F4BB'


def print_payload(bar1: str, label1: str, label2: str, payload: str, bar2: str) -> None:
    print(bar1)
    print('\n')
    print(f'{INDENT}{LEGEND}{label1.center(WIDTH)}{RESET}')
    if label2 != '':
        print(f'{INDENT}{LEGEND}{label2.center(WIDTH)}{RESET}')
    print(f'{INDENT}{FAINT}▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼{RESET}')
    print(f'{INDENT}{payload}')
    print(f'{INDENT}{FAINT}▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲{RESET}')
    print(f'{INDENT}{FAINT}1 3 5 7 9 1 3 5 7 9 1 3 5 7 9{RESET}')
    print('\n')
    if bar2:
        print(bar2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'payload',
        choices=['dash-integral', 'spaced-dash-integral', 'arab-ligature'],
    )
    options = parser.parse_args()

    bar = mkbar()
    label1, label2 = mklabels()

    payload2 = None
    if options.payload == 'arab-ligature':
        payload1 = '\uFDFD'
    elif options.payload == 'spaced-dash-integral':
        payload1 = ' {FAINT}█{RESET} '.join(mkprefix(w) for w in range(3))
    elif options.payload == 'dash-integral':
        payload1 = mkprefix(0) + '\uFF0A𝔽𝕚𝕩𝕖𝕕-𝐖𝐢𝐝𝐭𝐡'
        payload2 = mkprefix(3) + f'{FAINT}█{RESET}\uFF0A{FAINT}█{RESET}𝔽𝕚𝕩𝕖𝕕-𝐖𝐢𝐝𝐭𝐡'
    else:
        raise ValueError(f'invalid payload "{options.payload}"')

    print_payload(bar, label1, label2, payload1, '' if payload2 else bar)
    if payload2:
        print_payload(bar, label1, label2, payload2, bar)

if __name__ == '__main__':
    main()
