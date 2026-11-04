#!/usr/bin/env python3
"""Update stars and citations independently, reporting either failure."""

from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parent


def main():
    failed = []
    for label, script in (('GitHub stars', 'publish_stars.py'),
                          ('Google Scholar citations', 'publish_scholar.py')):
        try:
            result = subprocess.run([sys.executable, str(SCRIPTS / script)], cwd=SCRIPTS.parent)
            if result.returncode:
                failed.append(label)
        except OSError as error:
            print(f'{label} update failed: {error}', file=sys.stderr)
            failed.append(label)
    if failed:
        print('Failed updates: ' + ', '.join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
