#!.venv/bin/python

import sys
import traceback
from typing import Never

from demicode.render import MalformedEscape, Renderer

def help() -> Never:
    print('Usage: ./qtty.py csi|esc|osc <argument-string>')
    print('    For csi, include the final character in the argument string')
    print('    For osc, the terminating `ESC \\` are automatically appended')
    sys.exit(1)

def main() -> None:
    if len(sys.argv) != 3:
        help()

    renderer = Renderer.new()

    _, fn, params = sys.argv

    if fn == 'csi':
        query = '\x1b['
    elif fn == 'esc':
        query = '\x1b'
    elif fn == 'osc':
        query = '\x1b]'
    else:
        help()

    query += params

    if fn == 'osc':
        query += '\x1b\\'

    try:
        response = str(renderer.query(query))[2:-1].replace('\\x1b', '<ESC>')
        print(f'Response: {response}')
    except TimeoutError:
        print('Query timed out')
    except KeyboardInterrupt:
        print('Query was interrupted')
    except MalformedEscape:
        print('Response was malformed')
    except Exception as x:
        traceback.print_exception(x)


if __name__ == '__main__':
    main()
