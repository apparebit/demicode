#!./venv/bin/python

from pathlib import Path
import sys
import traceback
from typing import Never

sys.path.insert(0, str(Path.cwd()))

from demicode.ui.render import MalformedEscape, Renderer

def help(renderer: Renderer) -> Never:
    renderer.writeln('Usage: ./qtty.py csi|esc|osc <argument-string>')
    renderer.writeln('    For csi, include the final character in the argument string')
    renderer.writeln('    For osc, the terminating `ESC \\` are automatically appended')
    sys.exit(1)

def main() -> None:
    renderer = Renderer.new()

    if len(sys.argv) != 3:
        help(renderer)

    _, fn, params = sys.argv

    if fn == 'csi':
        query = '\x1b['
    elif fn == 'esc':
        query = '\x1b'
    elif fn == 'osc':
        query = '\x1b]'
    else:
        help(renderer)

    query += params

    if fn == 'osc':
        query += '\x1b\\'

    try:
        raw_response = renderer.query(query)
        response = str(raw_response)[2:-1].replace('\\x1b', '<ESC>')
        renderer.writeln(f'Response: {response}')
    except TimeoutError:
        renderer.writeln('Query timed out')
    except KeyboardInterrupt:
        renderer.writeln('Query was interrupted')
    except MalformedEscape:
        renderer.writeln('Response was malformed')
    except Exception as x:
        traceback.print_exception(x)


if __name__ == '__main__':
    main()
