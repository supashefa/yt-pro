"""YT-Pro — entry point.

    python main.py

Everything real lives in the `ytpro` package. This file is deliberately named
main.py rather than ytpro.py: a module and a package with the same name in the
same folder shadow each other, which trips up both plain imports and PyInstaller.
"""

import sys


def main():
    from ytpro.ui.app import main as run
    run()


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        print(f"Missing dependency: {e}\n\n"
              f"Install requirements with:\n"
              f"    pip install -r requirements.txt", file=sys.stderr)
        raise SystemExit(1)
