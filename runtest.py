#!./venv/bin/python

import subprocess
import sys
import traceback
import unittest

from test.runtime import ResultAdapter, StyledStream


if __name__ == '__main__':
    successful = False
    stream = sys.stdout
    styled = StyledStream(stream)

    def println(s: str = '') -> None:
        if s:
            stream.write(s)
        stream.write('\n')
        stream.flush()

    try:
        println(styled.heading(styled.pad('§1  Type Checking')))
        subprocess.run('./node_modules/.bin/pyright', check=True)
        println()

        println(styled.heading(styled.pad('§2  Unit Testing')))
        runner = unittest.main(
            module='test',
            exit=False,
            testRunner=unittest.TextTestRunner(
                stream=stream,
                resultclass=ResultAdapter
            ),
        )
        successful = runner.result.wasSuccessful()

    except subprocess.CalledProcessError:
        println(styled.failure('demicode failed to type check!'))
        exit(1)
    except Exception as x:
        trace = traceback.format_exception(x)
        println(''.join(trace[:-1]))
        println(styled.err(trace[-1]))

    sys.exit(not successful)
