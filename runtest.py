#!./venv/bin/python

import os
import subprocess
import sys
import traceback
import unittest

from test.runtime import ResultAdapter, StyledStream, TIGHT_WIDTH


if __name__ == '__main__':
    successful = False
    stream = sys.stdout
    styled = StyledStream(stream)

    def println(s: str = '') -> None:
        if s:
            stream.write(s)
        stream.write('\n')
        stream.flush()

    def printbar(title: str) -> None:
        println()
        count = TIGHT_WIDTH - 4 - len(title) - 1
        println(f'─── {styled.sgr("3", title)} {"─" * count}')

    try:
        println(styled.heading(styled.pad('§0  Setup')))
        printbar('Python')
        println(f'    {sys.executable}')
        printbar('Python Path')
        for path in sys.path:
            println(f'    {path}')
        printbar('Current Directory')
        println(f'    {os.getcwd()}')
        printbar('Current Module')
        println(f'    {__file__}')
        println('\n')

        println(styled.heading(styled.pad('§1  Type Checking')))
        subprocess.run(['./node_modules/.bin/pyright'], check=True)
        println('\n')

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
