#!/usr/bin/env python3
"""Check a WHIP branch before it becomes a pull request, for what the maintainer fixed in earlier PRs.

    python -I pr_check.py <repo> [--base origin/main] [--head HEAD] [--waits]

Reads git objects only; the working tree is not touched. --waits also runs whip_core's `node dev/waits.js --check`
in a temporary worktree. Exit code 1 when anything is reported.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

CONVENTIONAL = re.compile(r'^(feat|fix|chore|docs|refactor|perf|test|style|build|ci|revert)(\([^)]+\))?!?: \S', re.I)
HISTORY = re.compile(
    r"\b(used to|no longer|any ?more|previously|formerly|was changed|we changed|now goes|now uses|now does|now is"
    r"|now sends|now gets|replac(?:e|es|ed) the|instead of the old|before (?:this|that|the change|the fix)"
    r"|the old (?:way|code|version)|implementation rot)\b", re.I)
LINE_COMMENT = {
    '.lua': re.compile(r'--(.*)$'),
    '.js': re.compile(r'(?://|/\*+)(.*)$'),
    '.mjs': re.compile(r'(?://|/\*+)(.*)$'),
    '.ts': re.compile(r'(?://|/\*+)(.*)$'),
    '.css': re.compile(r'/\*+(.*)$'),
    '.html': re.compile(r'(?:<!--|//|/\*+)(.*)$'),
}
BLOCKS = {
    '.lua': [(r'--\[=*\[', r'\]=*\]')],
    '.js': [(r'/\*', r'\*/')], '.mjs': [(r'/\*', r'\*/')], '.ts': [(r'/\*', r'\*/')], '.css': [(r'/\*', r'\*/')],
    '.html': [(r'<!--', r'-->'), (r'/\*', r'\*/')],
}
HANDLER = re.compile(r'^(\s*)(?:AddEventHandler|RegisterNetEvent)\(.*function\s*\([^)]*\)\s*$')
THREAD = re.compile(r'(?:Citizen\.)?CreateThread\(')
COMMAND = re.compile(r"""(?:devCommand|RegisterCommand|Whip\.command|registerCommand)\(\s*['"]([\w-]+)['"]""")
CMD_ERE = r'(devCommand|RegisterCommand|Whip\.command|registerCommand)\('
EXPORT = re.compile(r"""\bexports\(\s*['"](\w+)['"]""")
EXP_ERE = r'exports\('
OWN_EVENT = re.compile(r"""AddEventHandler\(\s*['"](whip_core:player:[\w:]+)['"]""")
BG_SHORT = re.compile(r'^\s*background\s*:\s*(?!.*(?:url\(|gradient\())[^;]+;')


def git(repo, *args, check=True):
    r = subprocess.run(['git', '-C', repo, *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode != 0:
        sys.exit('git %s failed: %s' % (' '.join(args), r.stderr.strip()))
    return r.stdout


def show(repo, rev, path):
    r = subprocess.run(['git', '-C', repo, 'show', '%s:%s' % (rev, path)], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return r.stdout if r.returncode == 0 else ''


def added_lines(repo, base, head):
    """{path: {line_number: text}} for every line the branch adds."""
    out, path, line = {}, None, 0
    for raw in git(repo, 'diff', '-U0', '--no-color', '%s...%s' % (base, head)).splitlines():
        if raw.startswith('+++ '):
            path = raw[6:] if raw.startswith('+++ b/') else None
        elif raw.startswith('@@'):
            m = re.search(r'\+(\d+)', raw)
            line = int(m.group(1)) if m else 0
        elif raw.startswith('+') and path:
            out.setdefault(path, {})[line] = raw[1:]
            line += 1
    return out


def check_commits(repo, base, head, report):
    for row in git(repo, 'log', '--format=%h%x09%P%x09%s', '%s..%s' % (base, head)).splitlines():
        sha, parents, subject = row.split('\t', 2)
        if len(parents.split()) > 1:
            report('commit', sha, 'merge commit: rebase on main instead of merging it in (%s)' % subject)
        elif not CONVENTIONAL.match(subject):
            report('commit', sha, 'not a conventional commit (feat: / fix: / chore: / docs:): "%s"' % subject)


def block_lines(text, ext):
    """Line numbers inside block comments, whose middle lines carry no comment mark."""
    out = set()
    for open_, close in BLOCKS.get(ext, []):
        for m in re.finditer(open_ + r'.*?' + close, text, re.S):
            out.update(range(text.count('\n', 0, m.start()) + 1, text.count('\n', 0, m.end()) + 2))
    return out


def check_comments(repo, head, added, report):
    for path, lines in added.items():
        ext = os.path.splitext(path)[1].lower()
        if ext not in LINE_COMMENT:
            continue
        inside = block_lines(show(repo, head, path), ext)
        for n, text in lines.items():
            m = LINE_COMMENT[ext].search(text)
            body = m.group(1) if m else (text if n in inside else None)
            h = body and HISTORY.search(body)
            if h:
                report(path, n, 'comment tells the code\'s history ("%s"): say what the code does now; the before '
                                'and after go in the PR description' % h.group(0))


def check_handler_threads(repo, head, added, report):
    for path, lines in added.items():
        if not path.endswith('.lua'):
            continue
        src = show(repo, head, path).splitlines()
        for i, line in enumerate(src):
            m = HANDLER.match(line)
            if not m:
                continue
            outer, body = m.group(1), None
            for j in range(i + 1, len(src)):
                t = src[j]
                if not t.strip() or t.strip().startswith('--'):
                    continue
                ind = t[:len(t) - len(t.lstrip())]
                if len(ind) <= len(outer):
                    break
                body = ind if body is None else body
                if ind == body and THREAD.match(t.strip()) and (j + 1) in lines:
                    report(path, j + 1, 'CreateThread straight inside an event handler: handlers already run in '
                                        'their own thread, Wait works there')


def check_own_events(repo, head, added, report):
    if not show(repo, head, 'server/character.lua'):
        return
    for path, lines in added.items():
        if not path.endswith('.lua'):
            continue
        for n, text in lines.items():
            m = OWN_EVENT.search(text)
            if m:
                report(path, n, 'whip_core listens to its own public event %s: use the internal hook it comes from '
                                '(e.g. Character.onLife) if there is one' % m.group(1))


def names(repo, rev, rx, ere):
    found = set()
    for line in git(repo, 'grep', '-h', '-E', ere, rev, '--', '*.lua', check=False).splitlines():
        found.update(rx.findall(line))
    return found


def check_duplicates(repo, base, added, report):
    base_cmds = names(repo, base, COMMAND, CMD_ERE)
    base_exports = names(repo, base, EXPORT, EXP_ERE)
    for path, lines in added.items():
        if not path.endswith('.lua'):
            continue
        for n, text in lines.items():
            for c in COMMAND.findall(text):
                bare = c[5:] if c.startswith('whip_') else c
                twins = {c, bare, 'whip_' + bare} & base_cmds
                if twins:
                    report(path, n, 'command "%s" duplicates %s on the base branch: the maintainer refuses aliases of '
                                    'commands the framework has' % (c, ', '.join(sorted(twins))))
            for e in EXPORT.findall(text):
                if e in base_exports:
                    report(path, n, 'export %s already exists on the base branch' % e)


def new_exports(repo, base, added):
    before = names(repo, base, EXPORT, EXP_ERE)
    out = {}
    for path, lines in added.items():
        if path.endswith('.lua'):
            for n, text in lines.items():
                for e in EXPORT.findall(text):
                    if e not in before:
                        out[e] = (path, n)
    return out


def check_docs(repo, head, exports, report):
    docs = show(repo, head, 'docs.html')
    types = show(repo, head, 'types/server.lua') + show(repo, head, 'types/client.lua')
    for e, (path, n) in sorted(exports.items()):
        if e.startswith('_'):
            continue
        if docs and ('id="%s"' % e.lower()) not in docs:
            report(path, n, 'new export %s has no export card in docs.html (id="%s")' % (e, e.lower()))
        if types and not re.search(r'\b%s\b' % re.escape(e), types):
            report(path, n, 'new export %s has no stub in types/' % e)


def check_waits(repo, head, report):
    if not show(repo, head, 'dev/waits.js'):
        return
    node = shutil.which('Claude-node') or shutil.which('node')
    if not node:
        report('dev/waits.js', 0, 'node not found: run `node dev/waits.js --check` yourself')
        return
    tmp = tempfile.mkdtemp(prefix='claude-prcheck-')
    wt = os.path.join(tmp, 'wt')
    try:
        git(repo, 'worktree', 'add', '--detach', wt, head)
        r = subprocess.run([node, 'dev/waits.js', '--check'], cwd=wt, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        if r.returncode != 0:
            msg = (r.stdout + r.stderr).strip().splitlines()
            report('dev/waits.js', 0, '--check failed (run `node dev/waits.js --write`): ' + ' | '.join(msg[:4]))
    finally:
        git(repo, 'worktree', 'remove', '--force', wt, check=False)
        shutil.rmtree(tmp, ignore_errors=True)


def check_background(repo, head, added, report):
    images = {}
    for path in git(repo, 'ls-tree', '-r', '--name-only', head).splitlines():
        if not path.endswith('.css'):
            continue
        sel = None
        for line in show(repo, head, path).splitlines():
            if '{' in line:
                sel = line.split('{')[0].strip() or sel
            if 'background-image' in line and sel:
                for s in sel.split(','):
                    images.setdefault(s.strip(), path)
    for path, lines in added.items():
        if not path.endswith('.css'):
            continue
        text = show(repo, head, path).splitlines()
        for n, line in lines.items():
            if not BG_SHORT.match(line):
                continue
            sel = None
            for i in range(min(n - 1, len(text) - 1), -1, -1):
                if '{' in text[i]:
                    sel = text[i].split('{')[0].strip()
                    break
            hit = [s.strip() for s in (sel or '').split(',') if s.strip() in images]
            if hit:
                report(path, n, '`background:` resets the background-image %s sets on %s: use background-color'
                                % (images[hit[0]], hit[0]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('repo')
    ap.add_argument('--base', default='origin/main')
    ap.add_argument('--head', default='HEAD')
    ap.add_argument('--waits', action='store_true', help="also run whip_core's dev/waits.js --check")
    a = ap.parse_args()
    found = []

    def report(where, at, msg):
        found.append((where, at, msg))

    added = added_lines(a.repo, a.base, a.head)
    check_commits(a.repo, a.base, a.head, report)
    check_comments(a.repo, a.head, added, report)
    check_handler_threads(a.repo, a.head, added, report)
    check_own_events(a.repo, a.head, added, report)
    check_duplicates(a.repo, a.base, added, report)
    check_docs(a.repo, a.head, new_exports(a.repo, a.base, added), report)
    check_background(a.repo, a.head, added, report)
    if a.waits:
        check_waits(a.repo, a.head, report)

    for where, at, msg in found:
        print('%s:%s: %s' % (where, at, msg))
    print('%d finding(s) on %s...%s' % (len(found), a.base, a.head))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
