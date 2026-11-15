#!/usr/bin/env python3
"""Is there a newer version of this skill?

Compares this copy's VERSION file with the one on GitHub (fozenistaken/whip-skill, main branch) and says what to do.
It only reads: it never downloads or changes the skill. Standard library only.

    python -I scripts/check_update.py          # one line: up to date / newer version / could not check
    python -I scripts/check_update.py --quiet  # prints only when a newer version exists

Exit code: 0 up to date (or could not check), 10 a newer version exists.
"""
import os
import sys
import urllib.request

REMOTE = 'https://raw.githubusercontent.com/fozenistaken/whip-skill/main/VERSION'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse(v):
    try:
        return tuple(int(p) for p in v.strip().split('.'))
    except ValueError:
        return None


def main():
    quiet = '--quiet' in sys.argv
    try:
        with open(os.path.join(HERE, 'VERSION'), encoding='utf-8') as f:
            local = f.read().strip()
    except OSError:
        print('No VERSION file in this copy: cannot tell which version it is.')
        return 0
    try:
        req = urllib.request.Request(REMOTE, headers={'User-Agent': 'whip-skill-update-check'})
        with urllib.request.urlopen(req, timeout=5) as r:
            remote = r.read().decode('utf-8', 'replace').strip()
    except Exception as e:  # offline, blocked, GitHub down: never an error for the user
        if not quiet:
            print('Could not check for updates (%s). This copy is %s.' % (type(e).__name__, local))
        return 0
    lv, rv = parse(local), parse(remote)
    if lv is None or rv is None or rv <= lv:
        if not quiet:
            print('The skill is up to date (%s).' % local)
        return 0
    print('A newer version of the WHIP skill exists: %s (this copy is %s).' % (remote, local))
    if os.path.isdir(os.path.join(HERE, '.git')):
        print('Update it with:  git -C "%s" pull' % HERE)
    else:
        print('Update it by downloading https://github.com/fozenistaken/whip-skill and replacing this folder: %s' % HERE)
    return 10


if __name__ == '__main__':
    sys.exit(main())
