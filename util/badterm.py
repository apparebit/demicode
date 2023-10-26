#!.venv/bin/python

import argparse
import sys

sys.path.insert(0, '')

from demicode.ui.terminal import report_terminal_version


CSI = '\x1b['
FAINT = f'{CSI}38;5;248m'
LEGEND = f'{CSI}3;38;5;240m'
ORANGE = f'{CSI}38;5;202m'
YELLOW = f'{CSI}38;5;220m'
BLUE = f'{CSI}38;5;63m'
RESET = f'{CSI}0m'
INDENT = '    '
PREFIX = '\u2E3B\u2A0C{sep}\U0001F9D1\u200D\U0001F4BB'


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser('badterm', 'usage: badterm [-hsx123]')
    parser.add_argument('-1', action='store_const', const=1, default=0, dest='spaces')
    parser.add_argument('-2', action='store_const', const=2, dest='spaces')
    parser.add_argument('-3', action='store_const', const=3, dest='spaces')
    parser.add_argument('-s', action='store_true', dest='star')
    parser.add_argument('-x', action='store_true', dest='extra')
    return parser


def main() -> None:
    options = parser().parse_args()

    sep = ' ' * options.spaces
    star = '\uFF0A'
    if options.star:
        star = f'{BLUE}█{RESET}{star}{BLUE}█{RESET}'
    if options.extra:
        payload = ''.join(PREFIX.format(sep=sep) for sep in ('', ' ', '  '))
    else:
        payload = f'\u2E3B\u2A0C{sep}\U0001F9D1\u200D\U0001F4BB{star}𝔽𝕚𝕩𝕖𝕕-𝐖𝐢𝐝𝐭𝐡'

    WIDTH = 29

    terminal, version = report_terminal_version()
    if terminal is None:
        label = ['Unknown Terminal']
    elif version is None:
        label = [terminal]
    elif len((combined := f'{terminal} ({version})')) <= WIDTH:
        label = [combined]
    else:
        label = [terminal, version]

    print('\n')
    print(f'{INDENT}{LEGEND}{label[0].center(WIDTH)}{RESET}')
    if len(label) == 2:
        print(f'{INDENT}{LEGEND}{label[1].center(WIDTH)}{RESET}')
    print(f'{INDENT}{FAINT}▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼{RESET}')
    print(f'{INDENT}{payload}')
    print(f'{INDENT}{FAINT}▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲{RESET}')
    print(f'{INDENT}{FAINT}1 3 5 7 9 1 3 5 7 9 1 3 5 7 9{RESET}')
    print('\n')

if __name__ == '__main__':
    main()
