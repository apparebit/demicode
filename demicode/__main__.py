import sys

def main() -> None:
    if sys.version_info < (3, 11, 0):
        version = '.'.join(str(v) for v in sys.version_info[:3])
        print(f'Error: You are trying to run demicode with Python {version},')
        print(f'but demicode requires Python 3.11.0 or later to run.')
        print(f"Please upgrade the Python version and then try again.")
        sys.exit(1)

    # Delay importing tool, so that the version check above always proceeds.
    from .tool import run
    sys.exit(run(sys.argv))

if __name__ == '__main__':
    main()
